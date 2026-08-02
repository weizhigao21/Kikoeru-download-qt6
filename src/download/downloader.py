import os
import socket
import subprocess
import threading
import time
import logging
from xmlrpc.client import ServerProxy
from .. import config as _config
from ..database.cache import get_http_session
from ..utils import strip_rj_prefix

logger = logging.getLogger(__name__)

_aria2_process = None
_aria2_lock = threading.Lock()


def check_aria2_port(host="localhost", port=6800, timeout=2):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def ensure_aria2_running():
    global _aria2_process
    if check_aria2_port():
        return True
    with _aria2_lock:
        if check_aria2_port():
            return True
        aria2_exe = os.path.join(_config.ARIA2_DIR, "aria2.exe")
        if not os.path.exists(aria2_exe):
            logger.warning("[Aria2] 未找到: %s", aria2_exe)
            return False
        try:
            logger.info("[Aria2] 正在启动...")
            # 移除 shell=True：列表参数 + shell=True 语义混乱，v1.48.0 声称已修复但实际残留
            _aria2_process = subprocess.Popen(
                [aria2_exe],
                cwd=_config.ARIA2_DIR,
            )
            for _ in range(20):
                time.sleep(0.5)
                if check_aria2_port():
                    logger.info("[Aria2] 已就绪")
                    return True
            logger.warning("[Aria2] 启动超时")
            return False
        except Exception as e:
            logger.exception("[Aria2] 启动失败")
            return False


class WorkDownloader:
    def __init__(self, work, download_history):
        self.work = work
        self.download_history = download_history
        self._save_dir = None

    def _get_save_dir(self):
        if self._save_dir is None:
            source_id = self.work.get("source_id", "")
            title = self.work.get("title", "未命名")
            illegal_chars = set(r'\/:*?"<>|')
            extra_chars = _config.FILENAME_FILTER_CHARS
            if extra_chars:
                illegal_chars |= set(extra_chars)
            safe_title = "".join(c for c in title if c not in illegal_chars)[:50]
            folder_name = f"{source_id}-{safe_title}"
            self._save_dir = os.path.join(_config.DOWNLOAD_DIR, folder_name)
            os.makedirs(self._save_dir, exist_ok=True)
        return self._save_dir

    def prepare_download_dir(self):
        return self._get_save_dir()

    def download_file(self, url: str, filename: str):
        save_dir = self._get_save_dir()
        self.save_cover_image(save_dir)
        self.save_tags(save_dir)
        s = _get_global_aria2_proxy()
        options = {"dir": save_dir, "out": filename}
        s.aria2.addUri([url], options)
        return save_dir

    def download_file_async(self, url: str, filename: str, subfolder: str = ""):
        save_dir = self._get_save_dir()
        if subfolder:
            save_dir = os.path.join(save_dir, subfolder)
            os.makedirs(save_dir, exist_ok=True)
        s = _get_global_aria2_proxy()
        options = {"dir": save_dir, "out": filename}
        gid = s.aria2.addUri([url], options)
        return save_dir, gid

    def save_cover_image(self, save_dir: str):
        # 使用 strip_rj_prefix 提取纯数字 ID（v1.55.0 已抽取到 utils）
        numeric_id = strip_rj_prefix(self.work.get("source_id", "")).lstrip("0")

        urls_to_try = []
        if numeric_id:
            urls_to_try.append(
                f"https://api.asmr-200.com/api/cover/{numeric_id}.jpg?type=main"
            )
        main_cover_url = self.work.get("mainCoverUrl", "")
        if main_cover_url:
            urls_to_try.append(main_cover_url)

        if not urls_to_try:
            logger.debug("[封面] URL 为空，跳过保存封面")
            return False

        for url in urls_to_try:
            try:
                session = get_http_session()
                response = session.get(url, timeout=30)
                if response.status_code == 200 and len(response.content) > 1024:
                    cover_path = os.path.join(save_dir, "封面.jpg")
                    with open(cover_path, 'wb') as f:
                        f.write(response.content)
                    logger.debug("[封面] 已保存到: %s (%d 字节)", cover_path, len(response.content))
                    return True
                else:
                    logger.debug("[封面] %s... 无效 (状态=%s, 大小=%d)",
                                 url[:60], response.status_code, len(response.content))
            except Exception as e:
                logger.debug("[封面] 请求失败: %s... -> %s", url[:60], e)

        logger.debug("[封面] 所有封面 URL 均失败")
        return False

    def save_tags(self, save_dir: str):
        tags = self._extract_tags()
        if not tags:
            return False

        try:
            tags_path = os.path.join(save_dir, "标签.txt")
            with open(tags_path, 'w', encoding='utf-8') as f:
                f.write(" ".join(tags))
            return True
        except Exception:
            logger.exception("保存标签失败")
        return False

    def save_to_history(self):
        try:
            source_id = self.work.get("source_id", "")
            title = self.work.get("title", "")

            tags = self._extract_tags()
            cv_names = self._extract_cv_names()

            circle = self.work.get("circle", {})
            circle_name = circle.get("name", "") if isinstance(circle, dict) else ""

            thumbnail_url = self.work.get("thumbnailCoverUrl", "")
            main_cover_url = self.work.get("mainCoverUrl", "")
            vas = self.work.get("vas", [])
            circle_data = self.work.get("circle", {})
            other_editions = self.work.get("other_language_editions_in_db", [])

            self.download_history.add_download(
                source_id, title, tags, cv_names, circle_name,
                thumbnail_url, main_cover_url, vas, circle_data, other_editions
            )
            return True
        except Exception:
            logger.exception("保存下载历史失败")
            return False

    def save_to_history_async(self):
        save_dir = self._get_save_dir()
        self.save_cover_image(save_dir)
        self.save_tags(save_dir)
        return self.save_to_history()

    def _extract_tags(self):
        tags = []
        for tag in self.work.get("tags", []):
            name = tag.get("i18n", {}).get("zh-cn", {}).get("name")
            if name:
                tags.append(name)
        return tags

    def _extract_cv_names(self):
        return [va.get("name", "") for va in self.work.get("vas", []) if va.get("name")]


_global_proxy = None
_global_proxy_lock = threading.Lock()


def _get_global_aria2_proxy():
    """获取全局 aria2 XML-RPC 代理（线程安全单例）。

    ServerProxy 本身是线程安全的，无需 thread-local 缓存。
    """
    global _global_proxy
    if _global_proxy is None:
        with _global_proxy_lock:
            if _global_proxy is None:
                _global_proxy = ServerProxy(_config.ARIA2_RPC_URL, allow_none=True)
    return _global_proxy


_gid_error_counts = {}
_gid_error_lock = threading.Lock()


def poll_download_progress(gids):
    global _gid_error_counts
    if not gids:
        return 0, 0, 0, False
    try:
        s = _get_global_aria2_proxy()
        total = 0
        completed = 0
        speed = 0
        has_error = False
        finished_gids = []
        error_gids = []
        for gid in list(gids):
            try:
                status = s.aria2.tellStatus(gid)
                st = status.get("status", "")
                if st == "active":
                    completed += int(status.get("completedLength", 0))
                    total += int(status.get("totalLength", 0))
                    speed += int(status.get("downloadSpeed", 0))
                    with _gid_error_lock:
                        _gid_error_counts.pop(gid, None)
                elif st in ("waiting", "paused"):
                    total += int(status.get("totalLength", 0))
                elif st == "complete":
                    finished_gids.append(gid)
                    with _gid_error_lock:
                        _gid_error_counts.pop(gid, None)
                elif st == "error":
                    error_code = status.get("errorCode", "")
                    error_msg = status.get("errorMessage", "")
                    logger.warning("[Aria2] 下载错误 gid=%s code=%s msg=%s", gid, error_code, error_msg)
                    error_gids.append(gid)
                    has_error = True
                elif st == "removed":
                    error_gids.append(gid)
            except Exception as e:
                error_str = str(e)
                if "not found" in error_str.lower() or "GID" in error_str:
                    with _gid_error_lock:
                        _gid_error_counts[gid] = _gid_error_counts.get(gid, 0) + 1
                        if _gid_error_counts[gid] >= 3:
                            error_gids.append(gid)
                            has_error = True
                            _gid_error_counts.pop(gid, None)
        for gid in finished_gids:
            gids.discard(gid)
        for gid in error_gids:
            gids.discard(gid)
        return total, completed, speed, has_error
    except Exception:
        logger.exception("[Aria2] 轮询异常")
        return 0, 0, 0, False


def get_downloader(work, download_history) -> WorkDownloader:
    return WorkDownloader(work, download_history)


def purge_aria2_downloads():
    try:
        s = _get_global_aria2_proxy()
        s.aria2.purgeDownloadResult()
        logger.info("[Aria2] 已清除下载结果缓存")
        return True
    except OSError:
        # Aria2 未运行时连接被拒绝（如已切换到直接下载模式），清理操作可安全跳过
        logger.debug("[Aria2] 清除缓存跳过：Aria2 未运行")
        return False
    except Exception:
        logger.exception("[Aria2] 清除缓存失败")
        return False


def remove_aria2_downloads(gids):
    if not gids:
        return True
    try:
        s = _get_global_aria2_proxy()
        for gid in list(gids):
            try:
                s.aria2.remove(gid)
            except Exception:
                pass
            try:
                s.aria2.removeDownloadResult(gid)
            except Exception:
                pass
        logger.info("[Aria2] 已移除 %d 个下载任务", len(gids))
        return True
    except OSError:
        # Aria2 未运行时连接被拒绝，移除操作可安全跳过
        logger.debug("[Aria2] 移除任务跳过：Aria2 未运行")
        return False
    except Exception:
        logger.exception("[Aria2] 移除任务失败")
        return False
