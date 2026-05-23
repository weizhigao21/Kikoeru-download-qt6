import os
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional
from collections import deque


class TaskStatus(Enum):
    SUBMITTING = "submitting"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUEUED = "queued"


@dataclass
class DownloadTask:
    work_id: str
    title: str
    gids: set = field(default_factory=set)
    direct_task_ids: set = field(default_factory=set)
    total_files: int = 0
    total_bytes: int = 0
    completed_bytes: int = 0
    speed: int = 0
    status: TaskStatus = TaskStatus.SUBMITTING
    save_dir: str = ""
    created_at: float = 0.0
    completed_at: Optional[float] = None
    work: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    download_method: str = "aria2"


class DownloadManager:
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

    def set_download_history(self, dh):
        self.download_history = dh

    def set_queue_mode(self, enabled, max_concurrent=1):
        self._queue_mode = enabled
        self._max_concurrent = max(1, max_concurrent)

    def _get_active_count(self):
        with self._tasks_lock:
            return sum(1 for t in self.tasks.values()
                      if t.status in (TaskStatus.SUBMITTING, TaskStatus.DOWNLOADING))

    def _process_queue(self):
        if self._queue_processing:
            return
        self._queue_processing = True

        def queue_worker():
            while True:
                with self._queue_lock:
                    if not self._queue:
                        self._queue_processing = False
                        break

                    active_count = self._get_active_count()
                    if active_count >= self._max_concurrent:
                        time.sleep(1)
                        continue

                    work, files, task = self._queue.popleft()

                with self._tasks_lock:
                    task.status = TaskStatus.SUBMITTING

                self._notify_observers()
                threading.Thread(target=self._submit_task, args=(work, files, task), daemon=True).start()

                if self.download_history is not None:
                    threading.Thread(target=self._housekeeping, args=(work,), daemon=True).start()

        threading.Thread(target=queue_worker, daemon=True).start()

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

    def _submit_task(self, work, files, task):
        from .. import config as _config

        download_method = _config.DOWNLOAD_METHOD
        task.download_method = download_method

        if download_method == "direct":
            self._submit_direct(work, files, task)
        else:
            self._submit_aria2(work, files, task)

    def _submit_aria2(self, work, files, task):
        from .downloader import WorkDownloader, _get_global_aria2_proxy, ensure_aria2_running
        from .downloader_direct import check_file_exists

        if not ensure_aria2_running():
            with self._tasks_lock:
                task.status = TaskStatus.FAILED
            self._notify_observers()
            return

        downloader = WorkDownloader(work, None)
        save_dir = downloader.prepare_download_dir()
        task.save_dir = save_dir

        files_to_download = []
        skipped_count = 0

        for file_info in files:
            filename = file_info.get("filename", "未命名")
            subfolder = file_info.get("subfolder", "")
            url = file_info.get("url", "")
            file_dir = save_dir
            if subfolder:
                file_dir = os.path.join(save_dir, subfolder)
            filepath = os.path.join(file_dir, filename)

            is_complete, _ = check_file_exists(filepath, url)
            if is_complete:
                skipped_count += 1
                print(f"[下载] 文件已完整，跳过: {filename}")
            else:
                files_to_download.append(file_info)

        if skipped_count > 0:
            print(f"[下载] 跳过 {skipped_count} 个已完整文件，剩余 {len(files_to_download)} 个待下载")

        if not files_to_download:
            with self._tasks_lock:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                task.total_bytes = 0
                task.completed_bytes = 0
            self._notify_observers()
            return

        gids = set()
        subfolders_created = set()
        try:
            s = _get_global_aria2_proxy()
            for file_info in files_to_download:
                url = file_info.get("url")
                filename = file_info.get("filename", "未命名")
                subfolder = file_info.get("subfolder", "")
                try:
                    file_dir = save_dir
                    if subfolder:
                        file_dir = os.path.join(save_dir, subfolder)
                        if subfolder not in subfolders_created:
                            os.makedirs(file_dir, exist_ok=True)
                            subfolders_created.add(subfolder)
                    options = {"dir": file_dir, "out": filename}
                    gid = s.aria2.addUri([url], options)
                    if gid:
                        gids.add(gid)
                except Exception as e:
                    print(f"提交下载失败: {e}")
        except Exception as e:
            print(f"Aria2连接失败: {e}")

        with self._tasks_lock:
            task.gids = gids
            if gids:
                task.status = TaskStatus.DOWNLOADING
            else:
                task.status = TaskStatus.FAILED
        self._notify_observers()

        if gids:
            self._ensure_polling()

    def _submit_direct(self, work, files, task):
        from .downloader import WorkDownloader
        from .downloader_direct import check_file_exists
        from .. import config as _config

        downloader = WorkDownloader(work, None)
        save_dir = downloader.prepare_download_dir()
        task.save_dir = save_dir

        files_to_download = []
        skipped_count = 0

        for file_info in files:
            filename = file_info.get("filename", "未命名")
            subfolder = file_info.get("subfolder", "")
            url = file_info.get("url", "")
            file_dir = save_dir
            if subfolder:
                file_dir = os.path.join(save_dir, subfolder)
            filepath = os.path.join(file_dir, filename)

            is_complete, _ = check_file_exists(filepath, url)
            if is_complete:
                skipped_count += 1
                print(f"[下载] 文件已完整，跳过: {filename}")
            else:
                files_to_download.append(file_info)

        if skipped_count > 0:
            print(f"[下载] 跳过 {skipped_count} 个已完整文件，剩余 {len(files_to_download)} 个待下载")

        if not files_to_download:
            with self._tasks_lock:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                task.total_bytes = 0
                task.completed_bytes = 0
            self._notify_observers()
            return

        task_ids = set()
        max_threads = _config.DIRECT_DOWNLOAD_THREADS

        def download_sequential(file_list, task_id_set):
            for i, file_info in enumerate(file_list):
                if task.status == TaskStatus.CANCELLED:
                    break
                task_id = f"{task.work_id}_{len(task_ids)}"
                task_ids.add(task_id)
                self._direct_download_file(file_info, save_dir, task_id)
                if i < len(file_list) - 1:
                    time.sleep(2)

        batch_size = max(1, len(files_to_download) // max_threads)
        batches = []
        for i in range(0, len(files_to_download), batch_size):
            batches.append(files_to_download[i:i + batch_size])

        threads = []
        for batch in batches:
            t = threading.Thread(
                target=download_sequential,
                args=(batch, task_ids),
                daemon=True
            )
            t.start()
            threads.append(t)
            time.sleep(1)

        with self._tasks_lock:
            task.direct_task_ids = task_ids
            task.gids = set()
            task.status = TaskStatus.DOWNLOADING
        self._notify_observers()

        self._ensure_polling()

    def _direct_download_file(self, file_info, save_dir, task_id):
        from .downloader_direct import DirectDownloader
        import uuid

        url = file_info.get("url")
        filename = file_info.get("filename", "未命名")
        subfolder = file_info.get("subfolder", "")

        file_dir = save_dir
        if subfolder:
            file_dir = os.path.join(save_dir, subfolder)
            os.makedirs(file_dir, exist_ok=True)

        downloader = DirectDownloader()
        downloader.download_file(url, file_dir, filename, task_id)

    def _ensure_polling(self):
        if self._polling_active:
            return
        self._polling_active = True
        self._polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._polling_thread.start()

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

    def _housekeeping(self, work):
        try:
            from .downloader import WorkDownloader
            downloader = WorkDownloader(work, self.download_history)
            downloader.save_to_history_async()
        except Exception as e:
            print(f"后台处理失败: {e}")

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
