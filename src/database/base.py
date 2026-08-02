"""数据库管理器基类，提供连接管理、线程安全和 JSON 容错的公共逻辑。

三个具体管理器（DatabaseManager/DownloadHistoryManager/PendingTaskManager）
继承本类，消除 _connect/close_all/_safe_json_load 的三处重复实现。
"""
import sqlite3
import json
import threading
import time
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_CONNECTION_TIMEOUT = 300


class BaseDatabaseManager:
    """数据库管理器基类。

    - threading.local 缓存每线程连接（避免跨线程使用）
    - 300 秒空闲后自动重连（防止 stale connection）
    - WAL + synchronous=NORMAL 提升并发写入性能
    - 全局连接注册表确保 close_all 能关闭所有线程的连接
    """

    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        # 全局连接注册表：{thread_id: conn}，close_all 时遍历关闭所有线程连接
        self._registry_lock = threading.Lock()
        self._all_conns = {}
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = getattr(self._local, 'conn', None)
        last_used = getattr(self._local, 'last_used', 0)
        tid = threading.get_ident()

        if conn is None or (time.time() - last_used > _CONNECTION_TIMEOUT):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                self._unregister_conn(tid)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-4096")
            self._local.conn = conn
            self._register_conn(tid, conn)

        self._local.last_used = time.time()

        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None
            self._unregister_conn(tid)
            raise

    def _register_conn(self, tid, conn):
        with self._registry_lock:
            self._all_conns[tid] = conn

    def _unregister_conn(self, tid):
        with self._registry_lock:
            self._all_conns.pop(tid, None)

    def close_all(self):
        """关闭所有线程的数据库连接（包括工作线程）。

        在主线程调用时，遍历全局注册表关闭所有线程的连接，
        避免 close_all 只关闭当前线程连接导致其他线程连接泄漏。
        """
        with self._registry_lock:
            conns = list(self._all_conns.values())
            self._all_conns.clear()
        for conn in conns:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _safe_json_load(s, default=None):
        """安全解析 JSON 字符串。

        Args:
            s: JSON 字符串（可能为 None/空/损坏）
            default: 解析失败时返回的默认值（[] 或 {}）；None 时返回 {}
        """
        if not s:
            return default if default is not None else {}
        try:
            data = json.loads(s)
            return data if isinstance(data, (list, dict)) else (default if default is not None else {})
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}

    def _init_db(self):
        """子类实现具体的建表逻辑"""
        raise NotImplementedError
