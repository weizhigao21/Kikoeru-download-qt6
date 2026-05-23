import threading
import time

from .models import TaskStatus


class DownloadPollMixin:
    def _poll_loop(self):
        while self._polling_active:
            with self._tasks_lock:
                snapshot = list(self.tasks.values())

            changed = False
            for task in snapshot:
                if task.status != TaskStatus.DOWNLOADING:
                    continue

                if task.download_method == "direct":
                    if not task.direct_task_ids:
                        continue
                    self._poll_direct_task(task)
                else:
                    if not task.gids:
                        continue
                    self._poll_aria2_task(task)

                changed = True

            if changed:
                self._notify_observers()

            self._cleanup_counter += 1
            if self._cleanup_counter >= 10 or (time.time() - self._last_cleanup_time > 300):
                self._cleanup_completed_tasks()
                self._cleanup_counter = 0
                self._last_cleanup_time = time.time()

            with self._tasks_lock:
                any_active = any(
                    t.status in (TaskStatus.DOWNLOADING, TaskStatus.SUBMITTING)
                    for t in self.tasks.values()
                )

            if not any_active:
                self._polling_active = False
                break

            time.sleep(1)

    def _poll_direct_task(self, task):
        from .downloader_direct import poll_direct_progress

        if not task.direct_task_ids:
            return

        total, completed, speed, has_error = poll_direct_progress(task.direct_task_ids)

        with self._tasks_lock:
            task.total_bytes = total
            task.completed_bytes = completed
            task.speed = speed

            all_done = len(task.direct_task_ids) == 0
            progress_complete = total > 0 and completed >= total

            if all_done or progress_complete:
                if has_error and completed == 0:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self._sync_task_status(task)
            self._slow_speed_tracker.pop(task.work_id, None)

        if task.status == TaskStatus.DOWNLOADING:
            self._check_slow_speed(task)

    def _poll_aria2_task(self, task):
        old_gids_count = len(task.gids)
        total, completed, speed, has_error = self._poll_task_progress(task)
        new_gids_count = len(task.gids)

        with self._tasks_lock:
            task.total_bytes = total
            task.completed_bytes = completed
            task.speed = speed

            if new_gids_count == 0:
                if has_error and total == 0 and completed == 0:
                    if not hasattr(task, '_retry_count'):
                        task._retry_count = 0
                    task._retry_count += 1
                    if task._retry_count <= 3:
                        threading.Thread(
                            target=self._retry_task,
                            args=(task,),
                            daemon=True
                        ).start()
                    else:
                        task.status = TaskStatus.FAILED
                elif has_error and completed < total:
                    if not hasattr(task, '_retry_count'):
                        task._retry_count = 0
                    task._retry_count += 1
                    if task._retry_count <= 3:
                        threading.Thread(
                            target=self._retry_task,
                            args=(task,),
                            daemon=True
                        ).start()
                    else:
                        task.status = TaskStatus.FAILED
                elif not has_error and old_gids_count > 0:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                else:
                    task.status = TaskStatus.FAILED
            else:
                if has_error:
                    if not hasattr(task, '_consecutive_errors'):
                        task._consecutive_errors = 0
                    task._consecutive_errors += 1
                    if task._consecutive_errors >= 5:
                        if not hasattr(task, '_retry_count'):
                            task._retry_count = 0
                        task._retry_count += 1
                        if task._retry_count <= 3:
                            task._consecutive_errors = 0
                            threading.Thread(
                                target=self._retry_task,
                                args=(task,),
                                daemon=True
                            ).start()
                        else:
                            task.status = TaskStatus.FAILED
                else:
                    task._consecutive_errors = 0

                if task.status == TaskStatus.DOWNLOADING:
                    if not hasattr(task, '_last_progress_time'):
                        task._last_progress_time = time.time()
                    if not hasattr(task, '_last_completed'):
                        task._last_completed = 0
                    if completed > task._last_completed:
                        task._last_progress_time = time.time()
                        task._last_completed = completed
                    elif time.time() - task._last_progress_time > 120:
                        if not hasattr(task, '_retry_count'):
                            task._retry_count = 0
                        task._retry_count += 1
                        if task._retry_count <= 3:
                            task._last_progress_time = time.time()
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

    def _retry_task(self, task):
        import random

        wait_time = 5 + random.randint(0, 10)
        print(f"[重试] {task.work_id} 等待 {wait_time} 秒后重试 (第 {task._retry_count} 次)")
        time.sleep(wait_time)

        if task.download_method == "aria2":
            from .downloader import remove_aria2_downloads, purge_aria2_downloads
            remove_aria2_downloads(task.gids)
            purge_aria2_downloads()

        with self._tasks_lock:
            task.gids.clear()
            task.direct_task_ids.clear()
            task.total_bytes = 0
            task.completed_bytes = 0
            task.speed = 0

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
            print(f"[低速重启] {wid} 已达最大重启次数 ({self._MAX_SLOW_RESTARTS})，不再自动重启")
            self._slow_speed_tracker.pop(wid, None)
            return
        print(f"[低速重启] {wid} 低速持续 {slow_duration:.0f}s (速度: {task.speed / 1024:.0f} KB/s)，自动重启 (第{restart_count + 1}次)")
        self._slow_speed_tracker.pop(wid, None)
        self._slow_restart_count[wid] = restart_count + 1
        threading.Thread(target=self._auto_restart_slow_task, args=(task,), daemon=True).start()

    def _auto_restart_slow_task(self, task):
        with self._tasks_lock:
            current = self.tasks.get(task.work_id)
            if not current or current.status != TaskStatus.DOWNLOADING:
                return
        if task.download_method == "aria2":
            from .downloader import remove_aria2_downloads, purge_aria2_downloads
            remove_aria2_downloads(task.gids)
            purge_aria2_downloads()
        else:
            from .downloader_direct import _progress_lock, _download_progress
            with _progress_lock:
                for tid in list(task.direct_task_ids):
                    p = _download_progress.get(tid, {})
                    if p.get("status") not in ("complete", "error", "cancelled"):
                        _download_progress[tid] = {
                            **p, "status": "cancelled"
                        }
        with self._tasks_lock:
            task.gids.clear()
            task.direct_task_ids.clear()
            task.total_bytes = 0
            task.completed_bytes = 0
            task.speed = 0
            task.status = TaskStatus.SUBMITTING
        self._persist_task(task)
        self._submit_task(task.work, task.files, task)