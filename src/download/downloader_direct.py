import os
import threading
import time
import requests
from ..database.cache import get_http_session


_download_progress = {}
_progress_lock = threading.Lock()


def get_remote_file_size(url):
    try:
        session = get_http_session()
        response = session.head(url, timeout=10, allow_redirects=True)
        content_length = response.headers.get('content-length')
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
                print(f"[直接下载] 文件已完整，跳过: {filename}")
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
                if task_id:
                    with _progress_lock:
                        _download_progress[task_id]["status"] = "cancelled"
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
                            print(f"[直接下载] 文件已完整(416)，跳过: {filename}")
                            remote_size = get_remote_file_size(url)
                            final_size = remote_size if remote_size > 0 else local_offset
                            if task_id:
                                with _progress_lock:
                                    _download_progress[task_id]["total"] = final_size
                                    _download_progress[task_id]["completed"] = final_size
                                    _download_progress[task_id]["status"] = "complete"
                                    _download_progress[task_id]["speed"] = 0
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
                            print(f"[直接下载] 断点续传: {filename} ({local_offset}/{total_from_header})")
                        else:
                            print(f"[直接下载] 服务端不支持Range({response.status_code})，从头重新下载: {filename}")
                            response.close()
                            response = session.get(url, stream=True, timeout=30)
                    else:
                        response = session.get(url, stream=True, timeout=30)
                else:
                    response = session.get(url, stream=True, timeout=30)

                if response.status_code == 429:
                    wait_time = retry_wait * (2 ** attempt) + 5
                    print(f"[直接下载] 429 限流，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})")
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

                if task_id:
                    with _progress_lock:
                        _download_progress[task_id]["total"] = total_size

                downloaded = local_offset
                last_time = time.time()
                last_downloaded = downloaded
                update_interval = 0.3

                file_mode = 'ab' if (use_range and local_offset > 0) else 'wb'
                with open(filepath, file_mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._cancelled:
                            if task_id:
                                with _progress_lock:
                                    _download_progress[task_id]["status"] = "cancelled"
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

                                if task_id:
                                    with _progress_lock:
                                        _download_progress[task_id]["completed"] = downloaded
                                        _download_progress[task_id]["speed"] = speed

                final_total = total_size if total_size > 0 else downloaded
                if task_id:
                    with _progress_lock:
                        _download_progress[task_id]["status"] = "complete"
                        _download_progress[task_id]["total"] = final_total
                        _download_progress[task_id]["completed"] = final_total
                        _download_progress[task_id]["speed"] = 0

                return True

            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response.status_code == 429:
                    wait_time = retry_wait * (2 ** attempt) + 5
                    print(f"[直接下载] 429 限流，等待 {wait_time} 秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                print(f"[直接下载] 失败: {filename} - {e}")
                if task_id:
                    with _progress_lock:
                        _download_progress[task_id]["status"] = "error"
                return False

            except Exception as e:
                print(f"[直接下载] 失败: {filename} - {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_wait)
                    continue
                if task_id:
                    with _progress_lock:
                        _download_progress[task_id]["status"] = "error"
                return False

        if task_id:
            with _progress_lock:
                _download_progress[task_id]["status"] = "error"
        return False

    def cancel(self):
        self._cancelled = True


def get_download_progress(task_id):
    with _progress_lock:
        return _download_progress.get(task_id, {})


def clear_download_progress(task_id):
    with _progress_lock:
        _download_progress.pop(task_id, None)


def poll_direct_progress(task_ids):
    total = 0
    completed = 0
    speed = 0
    has_error = False
    error_count = 0
    unresolved = 0

    with _progress_lock:
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
                task_ids.discard(task_id)
            elif status == "downloading":
                unresolved += 1
                total += progress.get("total", 0)
                completed += progress.get("completed", 0)
                speed += progress.get("speed", 0)
            else:
                unresolved += 1

    all_resolved = (unresolved == 0)
    return total, completed, speed, has_error, error_count, all_resolved
