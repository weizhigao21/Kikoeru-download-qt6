import threading
import time
from collections import deque
from typing import Callable, Optional

from .models import TaskStatus, DownloadTask
from .manager_core import DownloadCoreMixin
from .manager_poll import DownloadPollMixin


class DownloadManager(DownloadCoreMixin, DownloadPollMixin):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.tasks: dict[str, DownloadTask] = {}
        self._tasks_lock = threading.Lock()
        self._polling_active = False
        self._polling_thread = None
        self._observers: list[Callable] = []
        self.download_history = None
        self._queue = deque()
        self._queue_lock = threading.Lock()
        self._queue_processing = False
        self._max_concurrent = 1
        self._queue_mode = False
        self._pending_db = None

        import src.config as _cfg
        self._SLOW_SPEED_THRESHOLD = _cfg.SLOW_SPEED_THRESHOLD * 1024 * 1024
        self._SLOW_SPEED_DURATION = _cfg.SLOW_SPEED_DURATION
        self._slow_speed_tracker: dict[str, float] = {}
        self._slow_restart_count: dict[str, int] = {}
        self._MAX_SLOW_RESTARTS = _cfg.MAX_SLOW_RESTARTS

        self._MAX_COMPLETED_TASKS = 100
        self._MAX_TOTAL_TASKS = 200
        self._cleanup_counter = 0
        self._last_cleanup_time = time.time()

    def set_download_history(self, dh):
        self.download_history = dh

    def set_pending_db(self, pdb):
        self._pending_db = pdb

    def set_queue_mode(self, enabled, max_concurrent=1):
        self._queue_mode = enabled
        self._max_concurrent = max(1, max_concurrent)

    def submit(self, work: dict, files: list[dict]) -> str:
        source_id = work.get("source_id", "")
        title = work.get("title", "未命名")
        work_id = source_id

        task = DownloadTask(
            work_id=work_id,
            title=title,
            total_files=len(files),
            created_at=time.time(),
            work=dict(work),
            files=list(files),
        )

        with self._tasks_lock:
            old_task = self.tasks.get(work_id)
            if old_task and old_task.status in (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
                return work_id
            self.tasks[work_id] = task

        self._persist_task(task)

        if self._queue_mode:
            with self._queue_lock:
                task.status = TaskStatus.QUEUED
                self._queue.append((work, files, task))
            self._notify_observers()
            self._process_queue()
        else:
            threading.Thread(target=self._submit_task, args=(work, files, task), daemon=True).start()
            if self.download_history is not None:
                threading.Thread(target=self._housekeeping, args=(work,), daemon=True).start()

        self._notify_observers()
        return work_id

    def cancel(self, work_id: str):
        with self._tasks_lock:
            task = self.tasks.get(work_id)
            if not task:
                return
            task.status = TaskStatus.CANCELLED

            if task.download_method == "aria2":
                gids = list(task.gids)
                task.gids.clear()
                try:
                    from .downloader import _get_global_aria2_proxy
                    s = _get_global_aria2_proxy()
                    for gid in gids:
                        try:
                            s.aria2.remove(gid)
                        except Exception:
                            pass
                except Exception:
                    pass
            else:
                task.direct_task_ids.clear()

        with self._queue_lock:
            self._queue = deque(
                (w, f, t) for w, f, t in self._queue
                if t.work_id != work_id
            )

        self._remove_persisted(work_id)
        self._notify_observers()

    def retry(self, work_id: str) -> bool:
        with self._tasks_lock:
            task = self.tasks.get(work_id)
            if not task:
                return False
            if task.status in (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
                return False
            if not task.work or not task.files:
                return False

            if task.download_method == "aria2":
                from .downloader import remove_aria2_downloads, purge_aria2_downloads
                remove_aria2_downloads(task.gids)
                purge_aria2_downloads()

            task.gids.clear()
            task.direct_task_ids.clear()
            task.total_bytes = 0
            task.completed_bytes = 0
            task.speed = 0
            task.created_at = time.time()
            task.completed_at = None

        if self._queue_mode:
            with self._queue_lock:
                task.status = TaskStatus.QUEUED
                self._queue.append((task.work, task.files, task))
            self._notify_observers()
            self._process_queue()
        else:
            task.status = TaskStatus.SUBMITTING
            threading.Thread(
                target=self._submit_task,
                args=(task.work, task.files, task),
                daemon=True
            ).start()

        self._notify_observers()
        return True

    def get_task(self, work_id: str) -> Optional[DownloadTask]:
        with self._tasks_lock:
            return self.tasks.get(work_id)

    def get_all_tasks(self) -> list[DownloadTask]:
        with self._tasks_lock:
            return list(self.tasks.values())

    def get_active_tasks(self) -> list[DownloadTask]:
        with self._tasks_lock:
            return [t for t in self.tasks.values()
                    if t.status in (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING)]

    def get_queued_tasks(self) -> list[DownloadTask]:
        with self._tasks_lock:
            return [t for t in self.tasks.values()
                    if t.status == TaskStatus.QUEUED]

    def get_queue_size(self) -> int:
        with self._queue_lock:
            return len(self._queue)

    def is_queue_mode(self) -> bool:
        return self._queue_mode

    def restore_pending_tasks(self):
        if self._pending_db is None:
            return
        try:
            pending_list = self._pending_db.get_all_pending()
            restored_count = 0
            for item in pending_list:
                work_id = item.get("work_id", "")
                if not work_id or work_id in self.tasks:
                    continue
                status_str = item.get("status", "failed")
                if status_str == "completed":
                    self._pending_db.remove_task(work_id)
                    continue

                task = DownloadTask(
                    work_id=work_id,
                    title=item.get("title", "未命名"),
                    total_files=len(item.get("files", [])),
                    created_at=item.get("created_at", time.time()),
                    work=item.get("work", {}),
                    files=item.get("files", []),
                    save_dir=item.get("save_dir", ""),
                    download_method=item.get("download_method", "aria2"),
                )

                if status_str in ("submitting", "downloading", "queued"):
                    task.status = TaskStatus.FAILED
                else:
                    try:
                        task.status = TaskStatus(status_str)
                    except ValueError:
                        task.status = TaskStatus.FAILED

                with self._tasks_lock:
                    self.tasks[work_id] = task

                self._persist_task(task)
                restored_count += 1

            if restored_count > 0:
                print(f"[持久化] 恢复 {restored_count} 个未完成下载任务")
                self._notify_observers()
            return restored_count
        except Exception as e:
            print(f"[持久化] 恢复任务失败: {e}")
            return 0

    def clear_pending_task(self, work_id: str):
        with self._tasks_lock:
            task = self.tasks.pop(work_id, None)
        if task:
            self._remove_persisted(work_id)
            self._notify_observers()
            return True
        return False

    def clear_all_pending(self):
        with self._tasks_lock:
            work_ids = [
                wid for wid, t in self.tasks.items()
                if t.status in (TaskStatus.FAILED, TaskStatus.SUBMITTING,
                                TaskStatus.DOWNLOADING, TaskStatus.QUEUED)
            ]
            for wid in work_ids:
                del self.tasks[wid]
        if self._pending_db:
            try:
                self._pending_db.clear_all()
            except Exception as e:
                print(f"[持久化] 清除所有待处理任务失败: {e}")
        self._notify_observers()

    def _cleanup_completed_tasks(self):
        with self._tasks_lock:
            total_tasks = len(self.tasks)
            if total_tasks <= self._MAX_TOTAL_TASKS:
                return

            completed_tasks = [
                (k, v) for k, v in self.tasks.items()
                if v.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]

            completed_tasks.sort(key=lambda x: x[1].completed_at or 0, reverse=True)

            tasks_to_remove = completed_tasks[self._MAX_COMPLETED_TASKS:]
            for work_id, _ in tasks_to_remove:
                del self.tasks[work_id]

            if tasks_to_remove:
                print(f"[内存管理] 清理 {len(tasks_to_remove)} 个旧任务，当前任务数: {len(self.tasks)}")

    def add_observer(self, callback: Callable):
        self._observers.append(callback)

    def remove_observer(self, callback: Callable):
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self):
        for cb in self._observers:
            try:
                cb()
            except Exception as e:
                print(f"观察者通知失败: {e}")