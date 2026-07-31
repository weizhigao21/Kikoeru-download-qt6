import os
import threading
import time

from .models import TaskStatus


class DownloadCoreMixin:
    def _persist_task(self, task):
        if self._pending_db is None:
            return
        try:
            self._pending_db.save_task(task)
        except Exception as e:
            print(f"[持久化] 保存任务失败: {task.work_id} - {e}")

    def _remove_persisted(self, work_id):
        if self._pending_db is None:
            return
        try:
            self._pending_db.remove_task(work_id)
        except Exception as e:
            print(f"[持久化] 删除任务失败: {work_id} - {e}")

    def _sync_task_status(self, task):
        if self._pending_db is None:
            return
        try:
            self._pending_db.update_status(task.work_id, task.status)
        except Exception as e:
            print(f"[持久化] 更新状态失败: {task.work_id} - {e}")

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
            self._sync_task_status(task)
            self._on_task_completed(task)
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
        self._sync_task_status(task)
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
            self._sync_task_status(task)
            self._on_task_completed(task)
            self._notify_observers()
            return

        max_threads = _config.DIRECT_DOWNLOAD_THREADS

        # 预生成所有 task_id，让 _poll_direct_task 从一开始就能看到完整的文件列表，
        # 防止下载线程在文件间 2 秒间隙中未注册新 task_id 时，poll 误判 all_resolved=True
        total_to_download = len(files_to_download)
        task_ids = set()
        task_id_list = []
        for idx in range(total_to_download):
            tid = f"{task.work_id}_{idx}"
            task_ids.add(tid)
            task_id_list.append(tid)

        def download_sequential(file_list, start_index):
            for i, file_info in enumerate(file_list):
                if task.status == TaskStatus.CANCELLED:
                    break
                tid = task_id_list[start_index + i]
                self._direct_download_file(file_info, save_dir, tid)
                if i < len(file_list) - 1:
                    time.sleep(2)

        batch_size = max(1, (total_to_download + max_threads - 1) // max_threads)
        batches = []
        for idx in range(0, total_to_download, batch_size):
            batches.append((idx, files_to_download[idx:idx + batch_size]))

        threads = []
        for start_idx, batch in batches:
            t = threading.Thread(
                target=download_sequential,
                args=(batch, start_idx),
                daemon=True
            )
            t.start()
            threads.append(t)
            time.sleep(1)

        with self._tasks_lock:
            task.direct_task_ids = task_ids
            task.gids = set()
            task.download_threads = threads
            task.status = TaskStatus.DOWNLOADING
        self._notify_observers()

        self._ensure_polling()

    def _direct_download_file(self, file_info, save_dir, task_id):
        from .downloader_direct import DirectDownloader

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
            self._poll_wake_event.set()
            return
        self._polling_active = True
        self._polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._polling_thread.start()

    def _housekeeping(self, work):
        try:
            from .downloader import WorkDownloader
            downloader = WorkDownloader(work, self.download_history)
            downloader.save_to_history_async()
        except Exception as e:
            print(f"后台处理失败: {e}")