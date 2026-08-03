import tkinter as tk
from tkinter import ttk
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import ImageTk

from .list_card import ListCardMixin
from .fonts import TITLE

logger = logging.getLogger('list_mixin')


class ListMixin(ListCardMixin):

    def _init_list_pool(self):
        self._card_slots = []
        self._empty_widgets = []

    def show_loading(self):
        self._clear_pool_display()
        for attr in ('loading_label', 'loading_bar'):
            if hasattr(self, attr):
                w = getattr(self, attr)
                if w is not None:
                    try:
                        if w.winfo_exists():
                            if attr == 'loading_bar':
                                w.stop()
                            w.destroy()
                    except Exception:
                        pass
                setattr(self, attr, None)
        self.loading_label = ttk.Label(self.scrollable_frame, text="正在加载数据...",
                                       font=TITLE)
        self.loading_label.pack(pady=30)
        self.loading_bar = ttk.Progressbar(self.scrollable_frame, mode='indeterminate', length=200)
        self.loading_bar.pack(pady=10)
        self.loading_bar.start(10)

    def hide_loading(self):
        self.loading = False
        if hasattr(self, 'loading_label'):
            try:
                if self.loading_label.winfo_exists():
                    self.loading_label.destroy()
            except Exception:
                pass
            self.loading_label = None
        if hasattr(self, 'loading_bar'):
            try:
                if self.loading_bar.winfo_exists():
                    self.loading_bar.stop()
                    self.loading_bar.destroy()
            except Exception:
                pass
            self.loading_bar = None
        self._clear_pool_display()

    def _clear_pool_display(self):
        if hasattr(self, '_card_slots'):
            for slot in self._card_slots:
                try:
                    slot['frame'].pack_forget()
                except Exception:
                    pass
        if hasattr(self, '_empty_widgets'):
            for w in self._empty_widgets:
                try:
                    w.destroy()
                except Exception:
                    pass
            self._empty_widgets = []

    def _on_title_click(self, event):
        idx = event.widget._work_index
        if idx is not None:
            self.show_work_detail(idx)

    def _on_title_double_click(self, event):
        idx = event.widget._work_index
        if idx is not None and idx < len(self.works):
            display_title = self._get_display_title(idx)
            self.open_download_window(self.works[idx], display_title)

    def _on_img_click(self, event):
        idx = event.widget._work_index
        if idx is not None:
            self.show_work_detail(idx)

    def _on_img_double_click(self, event):
        idx = event.widget._work_index
        if idx is not None and idx < len(self.works):
            display_title = self._get_display_title(idx)
            self.open_download_window(self.works[idx], display_title)

    def _get_display_title(self, idx):
        if hasattr(self, '_card_slots') and idx < len(self._card_slots):
            slot = self._card_slots[idx]
            if slot.get('show_translated') and slot.get('translated_title'):
                return slot['translated_title']
        return None

    def _on_tag_click(self, event):
        tag = event.widget._tag_name
        if tag:
            self.search_by_tag(tag)

    def _on_edition_click(self, event):
        sid = event.widget._edition_sid
        if sid:
            self._search_by_edition_id(sid)

    def display_works_list(self):
        logger.debug("display_works_list 开始")
        if not hasattr(self, '_card_slots'):
            self._init_list_pool()

        self._clear_pool_display()

        if not self.works:
            self.display_empty_state()
            return

        thumbnails_to_fetch = []
        need_create = max(0, len(self.works) - len(self._card_slots))
        for _ in range(need_create):
            slot = self._create_slot()
            self._card_slots.append(slot)

        for idx, work in enumerate(self.works):
            slot = self._card_slots[idx]
            slot['frame'].pack(fill=tk.X, padx=5, pady=5)

        # 批量查询翻译缓存，避免每张卡片在 UI 线程单独执行一次 SQL
        work_ids = [str(w.get('id', '')) for w in self.works]
        translation_map = self.db.get_translated_titles(work_ids) if work_ids else {}

        for idx, work in enumerate(self.works):
            slot = self._card_slots[idx]
            thumb_url = self._update_slot(slot, idx, work, translation_map)
            if thumb_url:
                thumbnails_to_fetch.append((slot, thumb_url, idx))

        for i in range(len(self.works), len(self._card_slots)):
            try:
                self._card_slots[i]['frame'].pack_forget()
            except Exception:
                pass

        if thumbnails_to_fetch:
            threading.Thread(target=self._load_thumbnails_batch,
                             args=(thumbnails_to_fetch,), daemon=True).start()

        self._schedule_canvas_configure()

    def _load_thumbnails_batch(self, items):
        gen = getattr(self, '_nav_generation', 0)
        executor = self._thumb_pool

        def load_one(slot, url, idx):
            if getattr(self, '_nav_generation', 0) != gen:
                return None
            try:
                pil_img = self.image_cache._load_pil_from_url(url)
                if pil_img and getattr(self, '_nav_generation', 0) == gen:
                    return (slot, pil_img, url)
            except Exception:
                pass
            return None

        future_map = {executor.submit(load_one, slot, url, idx): (slot, url)
                      for slot, url, idx in items}

        for future in as_completed(future_map):
            result = future.result()
            if result and getattr(self, '_nav_generation', 0) == gen:
                self.root.after(0, self._update_single_thumbnail, *result)

    def _update_single_thumbnail(self, slot, pil_img, url):
        colors = getattr(self, 'COLORS', {"border": "#e0e0e0"})
        try:
            if slot['img_label'].winfo_exists():
                photo = ImageTk.PhotoImage(pil_img)
                slot['img_label'].config(image=photo, text="", bg=colors["border"])
                slot['img_label'].image = photo
                self.image_cache.memory_cache.put(f"thumb_{url}", photo)
        except Exception:
            pass

    def _update_thumbnail(self, img_label, img):
        try:
            if img_label.winfo_exists():
                img_label.config(image=img, text="")
                img_label.image = img
        except Exception:
            pass

    def display_empty_state(self):
        if not hasattr(self, '_empty_widgets'):
            self._empty_widgets = []
        empty_frame = tk.Frame(self.scrollable_frame, bg="#f0f0f0")
        empty_frame.pack(pady=50)
        tk.Label(empty_frame, text="暂无数据", font=TITLE,
                 foreground="gray", bg="#f0f0f0").pack()
        self._empty_widgets.append(empty_frame)

    def _on_frame_configure(self, event=None):
        if self._configure_pending:
            return
        self._configure_pending = True
        self.root.after(100, self._do_canvas_configure)

    def _schedule_canvas_configure(self):
        if not self._configure_pending:
            self._configure_pending = True
            self.root.after(100, self._do_canvas_configure)

    def _do_canvas_configure(self):
        self._configure_pending = False
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_root_resize(self, event=None):
        self._schedule_canvas_configure()