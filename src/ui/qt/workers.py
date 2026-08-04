# -*- coding: utf-8 -*-
"""后台 Worker（阶段 1-2）：分页数据 / 搜索 / 下载列表 / 详情 / 缩略图。

QObject + moveToThread 常驻后台线程；信号跨线程自动队列调度回主线程；
generation 校验丢弃过期批次（沿用 tkinter 版 _nav_generation 机制）。
"""
from PyQt6.QtCore import QByteArray, QObject, pyqtSignal, pyqtSlot


def pil_to_rgb_data(pil_img):
    """PIL Image → (RGB bytes, width, height)。

    用 bytes 跨线程传递（不可变、安全），主线程重建 QImage，
    避免 QImage 跨线程时像素缓冲生命周期竞态导致访问冲突。
    """
    img = pil_img.convert("RGB")
    return img.tobytes("raw", "RGB"), img.width, img.height


def _work_from_detail(data):
    """把 fetch_work_detail 返回的完整 dict 转为列表卡片所需的 work dict。"""
    return {
        "id": data.get("id"),
        "title": data.get("title", ""),
        "source_id": data.get("source_id", ""),
        "thumbnailCoverUrl": data.get("thumbnailCoverUrl", ""),
        "mainCoverUrl": data.get("mainCoverUrl", ""),
        "tags": data.get("tags", []),
        "vas": data.get("vas", []),
        "circle": data.get("circle", {}),
        "other_language_editions_in_db": data.get("other_language_editions_in_db", []),
    }


class DataWorker(QObject):
    """作品分页数据：推荐 tab 优先读 DB 缓存，miss 才走 API 并保存；最新 tab 直接 API。"""
    request = pyqtSignal(int, str, int)          # (page, tab, generation)
    search = pyqtSignal(str, object, int, int)   # (query_type, query[str|list], page, generation)
    downloads = pyqtSignal(str, int)             # (sort_key, generation)
    work_detail = pyqtSignal(str, int)           # (source_id, generation)
    loaded = pyqtSignal(int, list, int)          # (generation, works, max_page)
    search_loaded = pyqtSignal(int, list, int, str, object)  # (generation, works, max_page, query_type, query)
    downloads_loaded = pyqtSignal(int, list, str)         # (generation, works, sort_key)
    work_detail_loaded = pyqtSignal(int, dict)            # (generation, data)
    failed = pyqtSignal(int, str)                # (generation, error)

    def __init__(self, db, api, dl_history=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._api = api
        self._dl = dl_history

    @pyqtSlot(int, str, int)
    def fetch_works(self, page, tab, generation):
        try:
            if tab == "latest":
                works, max_page = self._api.fetch_latest_works_page(page)
            else:  # recommend：DB 缓存优先
                cached = self._db.get_works_by_page(page)
                if cached:
                    max_page = self._db.get_max_page()
                    self.loaded.emit(generation, cached, max_page)
                    return
                works, max_page = self._api.fetch_works_page(page)
                self._db.save_works(works, page)
            self.loaded.emit(generation, works, max_page)
        except Exception as e:
            self.failed.emit(generation, str(e))

    @pyqtSlot(str, object, int, int)
    def do_search(self, query_type, query, page, generation):
        try:
            if query_type == "id":
                data = self._api.fetch_work_detail(query)
                if not data:
                    self.search_loaded.emit(generation, [], 1, query_type, query)
                    return
                self.search_loaded.emit(generation, [_work_from_detail(data)], 1, query_type, query)
            elif query_type == "keyword":
                works, max_page = self._api.search_by_keyword(query, page)
                self.search_loaded.emit(generation, works, max_page, query_type, query)
            elif query_type == "circle":
                works, max_page = self._api.search_by_circle(query, page)
                self.search_loaded.emit(generation, works, max_page, query_type, query)
            elif query_type == "tag":
                # 多标签：query 为标签列表（tkinter 版多标签同样传列表给 API）
                works, max_page = self._api.search_by_tag(query, page)
                self.search_loaded.emit(generation, works, max_page, query_type, query)
            else:
                self.search_loaded.emit(generation, [], 1, query_type, query)
        except Exception as e:
            self.failed.emit(generation, str(e))

    @pyqtSlot(str, int)
    def load_downloads(self, sort_key, generation):
        try:
            works = self._dl.get_all_downloaded_works_full(sort_key)
            self.downloads_loaded.emit(generation, works, sort_key)
        except Exception as e:
            self.failed.emit(generation, str(e))

    @pyqtSlot(str, int)
    def fetch_detail(self, source_id, generation):
        try:
            data = self._api.fetch_work_detail(source_id)
            self.work_detail_loaded.emit(generation, data or {})
        except Exception as e:
            self.work_detail_loaded.emit(generation, {})


class ThumbnailWorker(QObject):
    """缩略图/详情大图：后台线程下载/磁盘缓存/PIL 解码 → RGB bytes 回主线程重建 QPixmap。"""
    request = pyqtSignal(list, int)                       # (urls, generation)
    thumb_ready = pyqtSignal(int, str, QByteArray, int, int)  # (generation, url, rgb, w, h)
    detail_request = pyqtSignal(str, int)                 # (url, generation)
    detail_ready = pyqtSignal(int, QByteArray, int, int)  # (generation, rgb, w, h)

    def __init__(self, image_cache, parent=None):
        super().__init__(parent)
        self._cache = image_cache
        self._cancel_gen = -1

    @pyqtSlot(list, int)
    def load(self, urls, generation):
        self._cancel_gen = generation
        for url in urls:
            if generation != self._cancel_gen:
                return  # 新批次已到来，放弃剩余旧请求
            try:
                pil = self._cache._load_pil_from_url(url, (180, 180))
            except Exception:
                continue
            if pil is None:
                continue
            try:
                data, w, h = pil_to_rgb_data(pil)
                # QByteArray 是 Qt 内置 metatype，queued 跨线程可排队（深拷贝）
                self.thumb_ready.emit(generation, url, QByteArray(data), w, h)
            except Exception:
                continue

    @pyqtSlot(str, int)
    def load_detail(self, url, generation):
        """详情面板大图（400x400 上限）。"""
        try:
            pil = self._cache._load_pil_from_url(url, (400, 400))
            if pil is None:
                return
            data, w, h = pil_to_rgb_data(pil)
            self.detail_ready.emit(generation, QByteArray(data), w, h)
        except Exception:
            pass
