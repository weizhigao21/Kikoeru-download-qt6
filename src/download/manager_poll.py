import os
import threading
import time
import logging

from .models import TaskStatus

logger = logging.getLogger(__name__)


def _iter_tracks_leaves(tracks_data):
    """遍历 tracks 树 yield (subfolder, filename, url)。

    路径构造必须与 gui_download.py 的 DownloadWindow.process_node 保持一致：
    - folder: folder_path = current_path + title + "/"，递归子节点用 folder_path
    - leaf (audio/image/text): subfolder = current_path, filename = node.title
    - unknown: 递归 children，current_path 不变（不拼接 title）
    - tracks_data 可能是 list（多根）或 dict（单根），两种都处理
    """
    def walk(node, current_path):
        node_type = node.get("type", "")
        title = node.get("title", "")
        if node_type == "folder":
            folder_path = current_path + title + "/"
            for child in node.get("children", []):
                yield from walk(child, folder_path)
        elif node_type in ("audio", "image", "text"):
            url = node.get("mediaDownloadUrl") or node.get("mediaStreamUrl")
            yield (current_path, node.get("title", "未命名"), url)
        else:
            # unknown 类型：递归 children，current_path 不变（与 process_node 一致）
            for child in node.get("children", []):
                yield from walk(child, current_path)

    if isinstance(tracks_data, list):
        for node in tracks_data:
            yield from walk(node, "")
    else:
        yield from walk(tracks_data, "")


class DownloadPollMixin:
    def _poll_loop(self):
        idle_cycles = 0
        while self._polling_active:
            with self._tasks_lock:
                snapshot = list(self.tasks.values())

            has_downloading = False
            for task in snapshot:
                if task.status != TaskStatus.DOWNLOADING:
                    continue

                has_downloading = True
                if task.download_method == "direct":
                    if not task.direct_task_ids:
                        continue
                    self._poll_direct_task(task)
                else:
                    if not task.gids:
                        continue
                    self._poll_aria2_task(task)

            self._notify_observers()

            self._cleanup_counter += 1
            if self._cleanup_counter >= 10 or (time.time() - self._last_cleanup_time > 300):
                self._cleanup_completed_tasks()
                self._cleanup_counter = 0
                self._last_cleanup_time = time.time()

            # 检查活跃任务（使用实时状态，非快照）
            with self._tasks_lock:
                any_active = any(
                    t.status in (TaskStatus.DOWNLOADING, TaskStatus.SUBMITTING, TaskStatus.CONVERTING)
                    for t in self.tasks.values()
                )

            if not any_active:
                # 检查是否还有残留下载线程（使用实时状态）
                with self._tasks_lock:
                    threads_alive = any(
                        any(th.is_alive() for th in t.download_threads)
                        for t in self.tasks.values()
                        if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
                    )
                # 文件夹整理移出轮询线程（独立线程执行），避免阻塞其他任务进度轮询
                if not threads_alive and self._pending_flatten and not self._flattening:
                    self._flattening = True
                    threading.Thread(target=self._flatten_worker, daemon=True).start()

            # 动态睡眠间隔：有活跃任务时 1s，完全空闲时 30s
            if has_downloading:
                idle_cycles = 0
                sleep_time = 1
            elif not any_active:
                sleep_time = 30
            else:
                idle_cycles += 1
                sleep_time = min(2 + idle_cycles * 0.5, 5)

            self._poll_wake_event.wait(timeout=sleep_time)
            self._poll_wake_event.clear()

    def _flatten_worker(self):
        """文件夹整理后台线程：避免文件移动/删除阻塞全局轮询循环。"""
        try:
            self._do_pending_flatten()
        finally:
            self._flattening = False

    def _do_pending_flatten(self):
        """所有下载任务完成后，批量执行文件夹整理"""
        # 逐个处理：处理一个成功后才移除，防止中途失败丢失剩余目录
        while self._pending_flatten:
            save_dir = self._pending_flatten.pop(0)
            try:
                self._flatten_folders(save_dir)
            except Exception as e:
                logger.exception("[整理] 批量整理失败: %s: %s", save_dir, e)

    def _on_task_completed(self, task):
        """任务完成时的处理（不立即整理文件夹）"""
        # 兜底清理直接下载进度条目（覆盖"文件已存在直接完成"等旁路路径）
        self._cleanup_direct_progress(task)
        if task.save_dir:
            from .. import config as _config
            if _config.AUTO_FLATTEN_ENABLED:
                self._pending_flatten.append(task.save_dir)
        need_convert = _config.SUBTITLE_CONVERT_ENABLED or _config.TRADITIONAL_TO_SIMPLIFIED_ENABLED
        if need_convert:
            try:
                with self._tasks_lock:
                    task.status = TaskStatus.CONVERTING
                self._notify_observers()
                th = threading.Thread(
                    target=self._convert_subtitles_and_complete,
                    args=(task,),
                    # 非 daemon：程序退出前主窗口 closeEvent 会等待转换完成，
                    # 避免下载完成后的繁简转换被进程退出强杀导致繁体残留（v2.0.9）
                    daemon=False
                )
                with self._postprocess_lock:
                    self._postprocess_threads.add(th)
                th.start()
                return
            except Exception as e:
                logger.exception("[后处理] 启动失败: %s", e)
        with self._tasks_lock:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
        self._sync_task_status(task)
        self._remove_persisted(task.work_id)
        if self.download_history is not None and task.work:
            threading.Thread(target=self._housekeeping, args=(task.work,), daemon=True).start()
        self._notify_observers()
        # 唤醒轮询循环，让自动整理立即触发
        self._poll_wake_event.set()

    def _flatten_folders(self, save_dir):
        """将多层嵌套文件夹扁平化，只保留最后一层"""
        if not os.path.isdir(save_dir):
            return
        moved = 0
        failed = []
        for root, dirs, files in os.walk(save_dir):
            if root == save_dir:
                continue
            rel = os.path.relpath(root, save_dir)
            parts = rel.split(os.sep)
            if len(parts) <= 1:
                continue
            for filename in files:
                src = os.path.join(root, filename)
                dest_folder = os.path.join(save_dir, parts[-1])
                os.makedirs(dest_folder, exist_ok=True)
                dest = os.path.join(dest_folder, filename)
                if src == dest:
                    continue
                try:
                    if os.path.exists(dest):
                        os.remove(dest)
                    os.replace(src, dest)
                    moved += 1
                except Exception:
                    failed.append((src, dest))

        for src, dest in failed:
            for attempt in range(3):
                time.sleep(2)
                try:
                    if os.path.exists(dest):
                        os.remove(dest)
                    os.replace(src, dest)
                    moved += 1
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error("[整理] 移动失败(已重试3次): %s -> %s: %s", src, dest, e)

        if moved > 0:
            logger.info("[整理] 已整理 %d 个文件到根目录", moved)
            for root, dirs, files in os.walk(save_dir, topdown=False):
                if root == save_dir:
                    continue
                try:
                    if not os.listdir(root):
                        os.rmdir(root)
                except Exception:
                    pass

    def _convert_subtitles_and_complete(self, task):
        """转换字幕/繁简并标记任务完成"""
        from .. import config as _config

        try:
            # 字幕转换
            if _config.SUBTITLE_CONVERT_ENABLED:
                try:
                    from ..services.subtitle_converter import process_subtitle_in_directory
                    converted = process_subtitle_in_directory(task.save_dir)
                    if converted:
                        logger.info("[字幕] 转换完成: %d 个文件", len(converted))
                except Exception as e:
                    logger.exception("[字幕] 转换失败: %s", e)

            # 繁简转换
            if _config.TRADITIONAL_TO_SIMPLIFIED_ENABLED:
                try:
                    from ..services.text_converter import process_directory
                    result = process_directory(task.save_dir)
                    if result['content_converted'] or result['filename_converted']:
                        logger.info("[繁简] 转换完成: 内容 %d 个, 文件名 %d 个",
                                   len(result['content_converted']), len(result['filename_converted']))
                except Exception as e:
                    logger.exception("[繁简] 转换失败: %s", e)
        finally:
            # 从后处理线程登记中移除（当前线程）
            with self._postprocess_lock:
                self._postprocess_threads.discard(threading.current_thread())

        with self._tasks_lock:
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
        self._sync_task_status(task)
        self._remove_persisted(task.work_id)
        if self.download_history is not None and task.work:
            threading.Thread(target=self._housekeeping, args=(task.work,), daemon=True).start()
        self._notify_observers()
        # 唤醒轮询循环，让自动整理立即触发
        self._poll_wake_event.set()

    def _poll_direct_task(self, task):
        from .downloader_direct import poll_direct_progress

        if not task.direct_task_ids:
            return

        total, completed, speed, has_error, error_count, all_resolved = poll_direct_progress(task.direct_task_ids)

        with self._tasks_lock:
            # 防止进度条跳动：total 和 completed 均使用历史最大值，
            # 避免新文件加入时 total 突然增大导致百分比下降。
            task.peak_total_bytes = max(task.peak_total_bytes, total)
            task.total_bytes = task.peak_total_bytes
            task.completed_bytes = max(task.completed_bytes, completed)
            task.speed = speed

            # 未全部完成时，进度不超过 99.9%
            if not all_resolved and task.total_bytes > 0 and task.completed_bytes >= task.total_bytes:
                task.completed_bytes = task.total_bytes - 1

            if all_resolved:
                # 检查下载线程是否都已结束
                threads = task.download_threads
                if threads and any(th.is_alive() for th in threads):
                    # 线程还在运行，等待下一次轮询
                    pass
                elif has_error and completed == 0:
                    task.status = TaskStatus.FAILED
                elif has_error and error_count > 0:
                    task.retry_count += 1
                    if task.retry_count <= 3:
                        logger.info("[重试] %s 有 %s 个文件失败，自动重试 (第%d次)", task.work_id, error_count, task.retry_count)
                        threading.Thread(
                            target=self._retry_task,
                            args=(task,),
                            daemon=True
                        ).start()
                        return
                    else:
                        logger.warning("[下载] %s 达到最大重试次数，标记为失败", task.work_id)
                        task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self._sync_task_status(task)
            self._slow_speed_tracker.pop(task.work_id, None)
            self._slow_restart_count.pop(task.work_id, None)
            # 终态清理：释放该任务的直接下载进度条目，防止 _download_progress 无界增长
            self._cleanup_direct_progress(task)
            if task.status == TaskStatus.COMPLETED:
                self._on_task_completed(task)

        if task.status == TaskStatus.DOWNLOADING:
            self._check_slow_speed(task)

    def _cleanup_direct_progress(self, task):
        """清理任务在直接下载进度字典中的残留条目（正常完成/失败路径）。

        重试/低速重启路径由 _cleanup_and_reset_task 负责，这里覆盖正常终态，
        避免 _download_progress 随任务完成无限累积。
        """
        if task.download_method != "direct":
            return
        try:
            from .downloader_direct import _progress_lock, _download_progress
            with _progress_lock:
                for tid in list(task.direct_task_ids):
                    _download_progress.pop(tid, None)
        except Exception:
            logger.exception("[下载] 清理直接下载进度失败: %s", task.work_id)

    def _poll_aria2_task(self, task):
        old_gids_count = len(task.gids)
        total, completed, speed, has_error = self._poll_task_progress(task)
        new_gids_count = len(task.gids)

        with self._tasks_lock:
            task.total_bytes = total
            task.completed_bytes = completed
            task.speed = speed

            if new_gids_count == 0:
                if has_error and old_gids_count > 0:
                    task.retry_count += 1
                    if task.retry_count <= 3:
                        logger.info("[重试] %s 有文件下载失败，自动重试 (第%d次)", task.work_id, task.retry_count)
                        threading.Thread(
                            target=self._retry_task,
                            args=(task,),
                            daemon=True
                        ).start()
                    else:
                        logger.warning("[下载] %s 达到最大重试次数，标记为失败", task.work_id)
                        task.status = TaskStatus.FAILED
                elif not has_error and old_gids_count > 0:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                else:
                    task.status = TaskStatus.FAILED
            else:
                if has_error:
                    task.consecutive_errors += 1
                    if task.consecutive_errors >= 5:
                        task.retry_count += 1
                        if task.retry_count <= 3:
                            task.consecutive_errors = 0
                            threading.Thread(
                                target=self._retry_task,
                                args=(task,),
                                daemon=True
                            ).start()
                        else:
                            task.status = TaskStatus.FAILED
                else:
                    task.consecutive_errors = 0

                if task.status == TaskStatus.DOWNLOADING:
                    if completed > task.last_completed:
                        task.last_progress_time = time.time()
                        task.last_completed = completed
                    elif time.time() - task.last_progress_time > 120:
                        task.retry_count += 1
                        if task.retry_count <= 3:
                            task.last_progress_time = time.time()
                            threading.Thread(
                                target=self._retry_task,
                                args=(task,),
                                daemon=True
                            ).start()
                        else:
                            task.status = TaskStatus.FAILED
        self._sync_task_status(task)

        if task.status == TaskStatus.DOWNLOADING:
            self._check_slow_speed(task)
        elif task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self._slow_speed_tracker.pop(task.work_id, None)
            self._slow_restart_count.pop(task.work_id, None)
            if task.status == TaskStatus.COMPLETED:
                self._on_task_completed(task)

    def _cleanup_and_reset_task(self, task, thread_join_timeout):
        """清理旧下载线程和进度数据，重置 task 字段。

        _retry_task 和 _auto_restart_slow_task 共用的清理逻辑（v1.52.0 修复时两处重复）。

        Args:
            task: 要清理的下载任务
            thread_join_timeout: 等待旧下载线程的超时秒数（重试 30s，低速重启 120s）
        """
        # 等待旧下载线程结束，防止重复下载
        old_threads = task.download_threads
        if old_threads:
            for t in old_threads:
                t.join(timeout=thread_join_timeout)

        if task.download_method == "aria2":
            from .downloader import remove_aria2_downloads, purge_aria2_downloads
            remove_aria2_downloads(task.gids)
            purge_aria2_downloads()
        else:
            # 清理 _download_progress 中的旧进度记录，防止 poll 看到旧的 "error" 状态立即再次触发重试
            from .downloader_direct import _progress_lock, _download_progress
            with _progress_lock:
                for tid in list(task.direct_task_ids):
                    _download_progress.pop(tid, None)

        with self._tasks_lock:
            task.gids.clear()
            task.direct_task_ids.clear()
            task.total_bytes = 0
            task.completed_bytes = 0
            task.speed = 0
            task.download_threads = []
            task.peak_total_bytes = 0

    def _refresh_task_urls(self, task):
        """重新拉取 tracks 并刷新 task.files 的 url（URL 失效回退）。

        失败时返回 False 且不修改 task.files，退化为原重试行为。
        """
        source_id = task.work.get("source_id", "")
        if not source_id:
            return False
        try:
            from ..api_client import get_api_client
            new_tracks = get_api_client().fetch_tracks(source_id)
            if not new_tracks:
                return False
            if self.tracks_cache is not None:
                try:
                    self.tracks_cache.save_tracks(source_id, new_tracks, task.work.get("title", ""))
                except Exception:
                    logger.exception("[URL刷新] save_tracks 失败: %s", source_id)
            url_map = {}
            for subfolder, filename, url in _iter_tracks_leaves(new_tracks):
                if url:
                    url_map[(subfolder, filename)] = url
            if not url_map:
                return False
            refreshed = 0
            for f in task.files:
                new_url = url_map.get((f.get("subfolder", ""), f.get("filename", "未命名")))
                if new_url:
                    f["url"] = new_url
                    refreshed += 1
            logger.info("[URL刷新] %s 刷新 %d/%d 个 URL", source_id, refreshed, len(task.files))
            return refreshed > 0
        except Exception:
            logger.exception("[URL刷新] %s 失败，降级为原 URL", source_id)
            return False

    def _retry_task(self, task):
        import random

        wait_time = 5 + random.randint(0, 10)
        logger.info("[重试] %s 等待 %d 秒后重试 (第 %d 次)", task.work_id, wait_time, task.retry_count)
        time.sleep(wait_time)

        # 提取公共清理逻辑（重试等待 30s，低速重启 120s）
        self._cleanup_and_reset_task(task, thread_join_timeout=30)

        # URL 回退：仅首次自动重试刷新一次，无论成败都标记避免重复打 API
        if not task.urls_refreshed:
            task.urls_refreshed = True
            try:
                self._refresh_task_urls(task)
            except Exception:
                logger.exception("[重试] URL 刷新异常，降级")

        self._submit_task(task.work, task.files, task)

    def _poll_task_progress(self, task):
        from .downloader import poll_download_progress
        try:
            return poll_download_progress(task.gids)
        except Exception:
            return 0, 0, 0, True

    def _check_slow_speed(self, task):
        wid = task.work_id
        if task.speed >= self._SLOW_SPEED_THRESHOLD:
            self._slow_speed_tracker.pop(wid, None)
            return
        now = time.time()
        if wid not in self._slow_speed_tracker:
            self._slow_speed_tracker[wid] = now
            return
        slow_duration = now - self._slow_speed_tracker[wid]
        if slow_duration < self._SLOW_SPEED_DURATION:
            return
        restart_count = self._slow_restart_count.get(wid, 0)
        if restart_count >= self._MAX_SLOW_RESTARTS:
            logger.warning("[低速重启] %s 已达最大重启次数 (%d)，不再自动重启", wid, self._MAX_SLOW_RESTARTS)
            self._slow_speed_tracker.pop(wid, None)
            return
        logger.info("[低速重启] %s 低速持续 %.0fs (速度: %.0f KB/s)，自动重启 (第%d次)",
                    wid, slow_duration, task.speed / 1024, restart_count + 1)
        self._slow_speed_tracker.pop(wid, None)
        self._slow_restart_count[wid] = restart_count + 1
        threading.Thread(target=self._auto_restart_slow_task, args=(task,), daemon=True).start()

    def _auto_restart_slow_task(self, task):
        with self._tasks_lock:
            current = self.tasks.get(task.work_id)
            if not current or current.status != TaskStatus.DOWNLOADING:
                return

        # 提取公共清理逻辑（大文件低速下载可能需要较长时间，等待 120s）
        self._cleanup_and_reset_task(task, thread_join_timeout=120)

        with self._tasks_lock:
            task.status = TaskStatus.SUBMITTING
        self._persist_task(task)
        self._submit_task(task.work, task.files, task)

