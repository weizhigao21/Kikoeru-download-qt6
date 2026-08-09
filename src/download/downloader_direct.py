import os
import threading
import time
import logging
import requests
from ..database.cache import get_http_session

logger = logging.getLogger(__name__)

_download_progress = {}
_progress_lock = threading.Lock()


def _set_progress(task_id, **kwargs):
    """安全设置下载进度字段：如果 task_id 已被清理则静默跳过"""
    if not task_id:
        return
    with _progress_lock:
        entry = _download_progress.get(task_id)
        if entry is None:
            return
        entry.update(kwargs)


def get_remote_file_size(url):
    """获取远程文件大小，HEAD 失败时回退到 GET stream。

    某些 CDN 对 HEAD 请求返回 405，导致返回 -1 误判文件不完整重新下载。
    """
    session = get_http_session()
    try:
        response = session.head(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            content_length = response.headers.get('content-length')
            if content_length:
                return int(content_length)
    except Exception:
        pass
    # HEAD 失败（405 或异常）时回退到 GET stream，只读 content-length 不下载内容
    try:
        response = session.get(url, stream=True, timeout=10, allow_redirects=True)
        content_length = response.headers.get('content-length')
        response.close()
        if content_length:
            return int(content_length)
    except Exception:
        pass
    return -1


def check_file_exists(filepath, url=None):
    if not os.path.exists(filepath):
        return False, 0

    local_size = os.path.getsize(filepath)
    if local_size == 0:
        return False, 0

    if url:
        remote_size = get_remote_file_size(url)
        if remote_size > 0:
            return local_size == remote_size, local_size

    return local_size > 0, local_size


def _handle_429(response, attempt, max_retries):
    """处理 429 限流响应，优先读取 Retry-After 头，回退到指数退避。

    返回等待秒数（0 表示不等待）。
    """
    # 优先读取 Retry-After 头（v1.55.0 已在 api_client.py 修复，此处同步）
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        try:
            wait_time = min(int(retry_after), 60)
            logger.warning("[直接下载] 429 限流，Retry-After=%ss，等待 %ss 后重试 (%d/%d)",
                           retry_after, wait_time, attempt + 1, max_retries)
            return wait_time
        except (ValueError, TypeError):
            pass
    # 回退到指数退避
    wait_time = 3 * (2 ** attempt) + 5
    logger.warning("[直接下载] 429 限流，等待 %ss 后重试 (%d/%d)", wait_time, attempt + 1, max_retries)
    return wait_time


class DirectDownloader:
    def __init__(self):
        self._cancelled = False

    def download_file(self, url, save_dir, filename, task_id=None, skip_existing=True):
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, filename)

        if skip_existing:
            is_complete, file_size = check_file_exists(filepath, url)
            if is_complete:
                if task_id:
                    with _progress_lock:
                        _download_progress[task_id] = {
                            "total": file_size,
                            "completed": file_size,
                            "speed": 0,
                            "status": "complete"
                        }
                logger.info("[直接下载] 文件已完整，跳过: %s", filename)
                return True

        if task_id:
            with _progress_lock:
                _download_progress[task_id] = {
                    "total": 0,
                    "completed": 0,
                    "speed": 0,
                    "status": "downloading"
                }

        max_retries = 5
        retry_wait = 3

        for attempt in range(max_retries):
            if self._cancelled:
                _set_progress(task_id, status="cancelled")
                return False

            try:
                session = get_http_session()

                local_offset = 0
                use_range = False

                if os.path.exists(filepath):
                    local_offset = os.path.getsize(filepath)
                    if local_offset > 0:
                        headers = {"Range": f"bytes={local_offset}-"}
                        response = session.get(url, stream=True, timeout=30, headers=headers)

                        if response.status_code == 416:
                            logger.info("[直接下载] 文件已完整(416)，跳过: %s", filename)
                            remote_size = get_remote_file_size(url)
                            final_size = remote_size if remote_size > 0 else local_offset
                            _set_progress(task_id, total=final_size, completed=final_size, status="complete", speed=0)
                            return True

                        if response.status_code == 206:
                            use_range = True
                            content_range = response.headers.get('content-range', '')
                            total_from_header = 0
                            if content_range and '/' in content_range:
                                try:
                                    total_from_header = int(content_range.split('/')[-1])
                                except (ValueError, IndexError):
                                    pass
                            if total_from_header == 0:
                                total_from_header = get_remote_file_size(url)
                            logger.info("[直接下载] 断点续传: %s (%d/%d)", filename, local_offset, total_from_header)
                        else:
                            logger.info("[直接下载] 服务端不支持Range(%s)，从头重新下载: %s",
                                        response.status_code, filename)
                            response.close()
                            response = session.get(url, stream=True, timeout=30)
                    else:
                        response = session.get(url, stream=True, timeout=30)
                else:
                    response = session.get(url, stream=True, timeout=30)

                if response.status_code == 429:
                    wait_time = _handle_429(response, attempt, max_retries)
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()

                if use_range:
                    content_range = response.headers.get('content-range', '')
                    total_size = 0
                    if content_range and '/' in content_range:
                        try:
                            total_size = int(content_range.split('/')[-1])
                        except (ValueError, IndexError):
                            pass
                    if total_size == 0:
                        total_size = get_remote_file_size(url)
                else:
                    total_size = int(response.headers.get('content-length', 0))

                _set_progress(task_id, total=total_size)

                downloaded = local_offset
                last_time = time.time()
                last_downloaded = downloaded
                update_interval = 0.3

                file_mode = 'ab' if (use_range and local_offset > 0) else 'wb'
                with open(filepath, file_mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._cancelled:
                            _set_progress(task_id, status="cancelled")
                            return False

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            current_time = time.time()
                            elapsed = current_time - last_time
                            if elapsed >= update_interval:
                                speed = int((downloaded - last_downloaded) / elapsed)
                                last_time = current_time
                                last_downloaded = downloaded

                                _set_progress(task_id, completed=downloaded, speed=speed)

                final_total = total_size if total_size > 0 else downloaded
                _set_progress(task_id, status="complete", total=final_total, completed=final_total, speed=0)
                return True

            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                    # 关闭未消费的流式响应，避免连接句柄累积
                    try:
                        e.response.close()
                    except Exception:
                        pass
                    wait_time = _handle_429(e.response, attempt, max_retries)
                    time.sleep(wait_time)
                    continue
                logger.warning("[直接下载] 失败: %s - %s", filename, e)
                _set_progress(task_id, status="error")
                return False

            except Exception as e:
                logger.warning("[直接下载] 失败: %s - %s", filename, e)
                if attempt < max_retries - 1:
                    time.sleep(retry_wait)
                    continue
                _set_progress(task_id, status="error")
                return False

        _set_progress(task_id, status="error")
        return False

    def cancel(self):
        self._cancelled = True


def poll_direct_progress(task_ids):
    total = 0
    completed = 0
    speed = 0
    has_error = False
    error_count = 0
    unresolved = 0

    with _progress_lock:
        # 使用快照迭代，不修改原始 task_ids 集合（防止与 _submit_direct 的线程竞争）
        for task_id in list(task_ids):
            progress = _download_progress.get(task_id, {})
            status = progress.get("status", "")

            if status == "complete":
                task_total = progress.get("total", 0)
                task_completed = progress.get("completed", 0)
                total += task_total
                completed += task_completed if task_completed > 0 else task_total
            elif status in ("error", "cancelled"):
                has_error = True
                error_count += 1
            elif status == "downloading":
                unresolved += 1
                total += progress.get("total", 0)
                completed += progress.get("completed", 0)
                speed += progress.get("speed", 0)
            else:
                # status 为空（未开始下载或 task_id 尚未注册）
                unresolved += 1

    all_resolved = (unresolved == 0)
    return total, completed, speed, has_error, error_count, all_resolved

