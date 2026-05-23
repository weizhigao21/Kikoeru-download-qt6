from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


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