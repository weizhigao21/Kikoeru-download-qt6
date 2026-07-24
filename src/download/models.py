from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class TaskStatus(Enum):
    SUBMITTING = "submitting"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
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
    # 重试相关属性
    retry_count: int = 0
    consecutive_errors: int = 0
    # 进度跟踪属性
    peak_total_bytes: int = 0
    last_progress_time: float = 0.0
    last_completed: int = 0
    # 下载线程管理
    download_threads: list = field(default_factory=list)
