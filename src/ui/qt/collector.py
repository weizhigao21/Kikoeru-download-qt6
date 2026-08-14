# -*- coding: utf-8 -*-
"""自动采集后台线程（下载页功能）。

双轨调度：
- 头部追新（head_poll_interval 秒）：拉第 1 页 → 查 works 表 → 有新 ID 就入库；
- 游标补历史（3s）：推进游标扫历史（递增步长 + 回退锁定 + 每日上限）。

状态持久化到 works.db 的 collector_state 表，断点续扫、跨天计数归零但游标保持。
数据拉取注入短 TTL 缓存，绕过 api_client 的 120s 全局缓存，保证轮询拿到新数据。
"""
from datetime import date

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from src import config as _config
from src.api_client import _APICache, fetch_latest_works_page


class NewWorksPoller(QObject):
    """作品自动采集器（moveToThread 到独立 QThread 运行）。"""

    collected = pyqtSignal(int)       # 本次入库的新作品数
    statusChanged = pyqtSignal(str)   # 采集状态文案

    CURSOR_INTERVAL_MS = 3000         # 游标补历史间隔（需求原文 3s）
    STEP_SOFT_MAX = 20                # 跳页步长软上限

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        # 短 TTL 缓存：绕过全局 120s 缓存（ttl 很小，等同每次真实拉取）
        self._cache = _APICache(max_size=200, ttl=2)

        # 状态字段（从 collector_state 恢复）
        self.page = 1
        self.step = 1
        self.last_old = 0
        self.locked = 0
        self.today_count = 0
        self._today_date = date.today().isoformat()
        self._enabled = bool(_config.AUTO_COLLECT_ENABLED)
        self._busy = False
        self._load_state()

        # 游标定时器（补历史）
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(self.CURSOR_INTERVAL_MS)
        self._cursor_timer.timeout.connect(self._cursor_tick)

        # 头部定时器（追新）
        self._head_timer = QTimer(self)
        self._head_timer.setInterval(max(1, int(_config.HEAD_POLL_INTERVAL)) * 1000)
        self._head_timer.timeout.connect(self._head_tick)

    # ---------- 生命周期 ----------
    @pyqtSlot()
    def start(self):
        """线程启动后调用：启动定时器并发布初始状态。"""
        if self._enabled:
            self._cursor_timer.start()
            self._head_timer.start()
        self._emit_status()

    @pyqtSlot()
    def stop(self):
        """停止定时器并落盘状态（退出时调用）。"""
        self._cursor_timer.stop()
        self._head_timer.stop()
        self._save_state()

    # ---------- 状态持久化 ----------
    def _load_state(self):
        try:
            state = self._db.load_collector_state()
        except Exception:
            state = {}
        self.page = max(1, int(state.get("page", 1) or 1))
        self.step = max(1, int(state.get("step", 1) or 1))
        self.last_old = max(0, int(state.get("last_old", 0) or 0))
        self.locked = max(0, int(state.get("locked", 0) or 0))
        if state.get("date") == self._today_date:
            self.today_count = max(0, int(state.get("today_count", 0) or 0))
        else:
            self.today_count = 0  # 跨天：计数归零，游标保持

    def _save_state(self):
        try:
            self._db.save_collector_state({
                "page": self.page,
                "step": self.step,
                "last_old": self.last_old,
                "locked": self.locked,
                "today_count": self.today_count,
                "date": self._today_date,
            })
        except Exception:
            pass

    def _roll_date(self):
        """跨天检测：计数归零，游标保持（继续从上次位置扫，不回绕）。"""
        today = date.today().isoformat()
        if today != self._today_date:
            self._today_date = today
            self.today_count = 0

    def _wrap(self):
        """回绕到第 1 页。"""
        self.page = 1
        self.step = 1
        self.last_old = 0
        self.locked = 0

    # ---------- 限额 ----------
    def _limit(self):
        return int(_config.DAILY_NEW_WORKS_LIMIT)

    def _limit_reached(self):
        lim = self._limit()
        return lim > 0 and self.today_count >= lim

    def _emit_status(self):
        lim = self._limit()
        if lim > 0 and self.today_count >= lim:
            self.statusChanged.emit(f"采集：今日已达上限 {lim}，明日继续 · 游标第 {self.page} 页")
        else:
            show = f"{self.today_count}/{lim}" if lim > 0 else f"{self.today_count}/不限"
            self.statusChanged.emit(f"采集：今日入库 {show} · 游标第 {self.page} 页")

    # ---------- 头部追新 ----------
    @pyqtSlot()
    def _head_tick(self):
        if self._busy or not self._enabled:
            return
        self._roll_date()
        if self._limit_reached():
            return
        self._busy = True
        try:
            works, _max_page = fetch_latest_works_page(1, cache=self._cache)
            if not works:
                return
            new = self._new_works(works)
            if new:
                self._db.upsert_works(new, 1)
                self.today_count += len(new)
                self.collected.emit(len(new))
                self._save_state()
                self._emit_status()
        except Exception:
            pass
        finally:
            self._busy = False

    # ---------- 游标补历史 ----------
    @pyqtSlot()
    def _cursor_tick(self):
        if self._busy or not self._enabled:
            return
        self._roll_date()
        if self._limit_reached():
            return
        self._busy = True
        try:
            works, max_page = fetch_latest_works_page(self.page, cache=self._cache)
            if not works:
                self._wrap()          # 空页 = 越过末尾，回绕
                self._save_state()
                self._emit_status()
                return

            new = self._new_works(works)
            if not new:
                # 整页全有（旧数据）
                self.last_old = self.page
                if self.locked > 0:
                    # 回退锁定区间内：步长 1 逐页，避免再次跳过头
                    self.page += 1
                    if self.page > self.locked:
                        self.locked = 0
                else:
                    self.step = min(self.step + 1, self.STEP_SOFT_MAX)
                    self.page += self.step
            else:
                # 有新作品
                self._db.upsert_works(new, self.page)
                self.today_count += len(new)
                self.collected.emit(len(new))
                if self.step > 1:
                    # 跳页跳进来 → 回退到旧区末尾 +1 并锁步长，避免漏边界
                    self.locked = self.page
                    self.page = self.last_old + 1
                    self.step = 1
                else:
                    self.page += 1
                    self.step = 1

            # 越过最大页 → 回绕
            if max_page and max_page > 0 and self.page > max_page:
                self._wrap()
            self._save_state()
            self._emit_status()
        except Exception:
            pass
        finally:
            self._busy = False

    # ---------- 查重 ----------
    def _new_works(self, works):
        """返回 works 中 works 表里还没有的作品列表（按 work_id 查重）。"""
        ids = [str(w.get("id", "")) for w in works if w.get("id")]
        if not ids:
            return []
        existing = self._db.existing_work_ids(ids)
        return [w for w in works if str(w.get("id", "")) not in existing]

    # ---------- 外部控制（设置项生效） ----------
    @pyqtSlot(bool)
    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if self._enabled:
            if not self._cursor_timer.isActive():
                self._cursor_timer.start()
            if not self._head_timer.isActive():
                self._head_timer.start()
            self._emit_status()
        else:
            self._cursor_timer.stop()
            self._head_timer.stop()
            self.statusChanged.emit("采集：已暂停")

    @pyqtSlot(int)
    def set_head_interval(self, seconds):
        self._head_timer.setInterval(max(1, int(seconds)) * 1000)
