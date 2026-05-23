import tkinter as tk
from tkinter import ttk
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from PIL import ImageTk

from .. import config as _config
from ..services.translator import get_translator

logger = logging.getLogger('list_mixin')


class ListMixin:

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
                                       font=("Microsoft YaHei UI", 14))
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

    def _create_slot(self):
        colors = getattr(self, 'COLORS', {
            "bg": "#f5f5f5",
            "card_bg": "#ffffff",
            "primary": "#1976D2",
            "primary_light": "#E3F2FD",
            "accent": "#FF9800",
            "success": "#4CAF50",
            "error": "#F44336",
            "text": "#333333",
            "text_secondary": "#666666",
            "text_hint": "#999999",
            "border": "#e0e0e0",
        })

        frame = tk.Frame(self.scrollable_frame, bg=colors["card_bg"], relief=tk.SOLID, bd=1)
        item_frame = tk.Frame(frame, bg=colors["card_bg"])
        item_frame.pack(fill=tk.X, padx=8, pady=8)

        img_container = tk.Frame(item_frame, bg=colors["border"])
        img_container.pack(side=tk.LEFT, padx=(0, 12))

        img_label = tk.Label(img_container, text="加载中", bg=colors["border"], fg=colors["text_hint"],
                            font=("Microsoft YaHei UI", 9))
        img_label.pack(padx=2, pady=2)

        text_frame = tk.Frame(item_frame, bg=colors["card_bg"])
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        title_frame = tk.Frame(text_frame, bg=colors["card_bg"])
        title_frame.pack(fill=tk.X, pady=(0, 4))

        title_label = tk.Label(title_frame, text="", font=("Microsoft YaHei UI", 10, "bold"),
                               cursor="hand2", bg=colors["card_bg"], fg=colors["text"], anchor=tk.W, wraplength=380)
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        downloaded_label = tk.Label(title_frame, text="✓ 已下载", bg=colors["primary"], fg="white",
                                     font=("Microsoft YaHei UI", 8, "bold"), padx=6, pady=2)
        downloaded_label.pack(side=tk.LEFT, padx=(8, 0))
        downloaded_label.pack_forget()

        toggle_btn = tk.Button(title_frame, text="译", font=("Microsoft YaHei UI", 8),
                               relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                               bg=colors["primary_light"], fg=colors["primary"], width=2)
        toggle_btn.pack(side=tk.LEFT, padx=(4, 0))
        toggle_btn.pack_forget()

        edit_btn = tk.Button(title_frame, text="编辑", font=("Microsoft YaHei UI", 8),
                             relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                             bg="#FFF3E0", fg=colors["accent"], width=3)
        edit_btn.pack(side=tk.LEFT, padx=(3, 0))
        edit_btn.pack_forget()

        tags_wrapper = tk.Frame(text_frame, bg=colors["card_bg"])
        tags_wrapper.pack(anchor=tk.W, pady=(4, 0))
        tags_canvas = tk.Canvas(tags_wrapper, bg=colors["card_bg"], height=22, highlightthickness=0)
        tags_canvas.pack(anchor=tk.W, fill=tk.X)
        tags_canvas._tag_data = []

        id_frame = tk.Frame(text_frame, bg=colors["card_bg"])
        id_frame.pack(anchor=tk.W, pady=(6, 0))
        id_label = tk.Label(id_frame, text="", font=("Microsoft YaHei UI", 9),
                            foreground=colors["primary"], bg=colors["card_bg"], anchor=tk.W)
        id_label.pack(side=tk.LEFT)
        id_label.bind("<Button-1>", self._on_title_click)

        copy_btn = tk.Button(id_frame, text="📋", font=("Segoe UI Emoji", 10),
                             relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                             bg=colors["card_bg"], fg=colors["text_secondary"])
        copy_btn.pack(side=tk.LEFT, padx=(8, 0))

        translate_btn = tk.Button(id_frame, text="翻译", font=("Microsoft YaHei UI", 9),
                                  relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                                  bg=colors["card_bg"], fg=colors["success"])
        translate_btn.pack(side=tk.LEFT, padx=(4, 0))

        editions_container = tk.Frame(id_frame, bg=colors["card_bg"])
        editions_container.pack(side=tk.LEFT, padx=(8, 0))

        title_label.bind("<Button-1>", self._on_title_click)
        title_label.bind("<Double-Button-1>", self._on_title_double_click)
        img_label.bind("<Button-1>", self._on_img_click)
        img_label.bind("<Double-Button-1>", self._on_img_double_click)

        slot = {
            'frame': frame,
            'img_label': img_label,
            'title_label': title_label,
            'toggle_btn': toggle_btn,
            'edit_btn': edit_btn,
            'tags_label': tags_canvas,
            'id_label': id_label,
            'copy_btn': copy_btn,
            'translate_btn': translate_btn,
            'downloaded_label': downloaded_label,
            'editions_container': editions_container,
            'current_work': None,
            'original_title': '',
            'translated_title': '',
            'show_translated': False,
        }
        return slot

    def _draw_tags_on_canvas(self, canvas, tags):
        canvas.delete("all")
        canvas._tag_data = []
        if not tags:
            canvas.configure(height=0)
            return
        cw = canvas.winfo_width()
        if not cw or cw < 50:
            try:
                mw = canvas.master.winfo_width()
                cw = mw if mw and mw >= 50 else 480
            except Exception:
                cw = 480
        TAG_COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#E91E63",
                       "#00BCD4", "#8BC34A", "#FF5722"]
        x, y = 2, 2
        row_height = 26
        max_width = cw - 4
        for idx, tag in enumerate(tags[:12]):
            color = TAG_COLORS[idx % len(TAG_COLORS)]
            text_id = canvas.create_text(0, 0, text=tag, font=("Microsoft YaHei UI", 9), anchor="nw")
            bbox = canvas.bbox(text_id)
            tw = bbox[2] - bbox[0] + 12
            canvas.delete(text_id)
            if idx > 0 and x + tw > max_width:
                x = 2
                y += row_height
            rect_id = canvas.create_rectangle(
                x, y, x + tw, y + 20, fill=color, outline=color, width=0)
            text_id = canvas.create_text(
                x + tw // 2, y + 10, text=tag, font=("Microsoft YaHei UI", 9),
                fill="white", anchor="center")
            canvas._tag_data.append((rect_id, text_id, tag))
            x += tw + 6
        canvas.configure(height=y + row_height)
        canvas.tag_bind("all", "<Button-1>", self._on_canvas_tag_click)

    def _on_canvas_tag_click(self, event):
        widget = event.widget
        if not hasattr(widget, '_tag_data'):
            return
        for rect_id, text_id, tag in widget._tag_data:
            coords = widget.coords(rect_id)
            if coords and coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.search_by_tag(tag)
                return

    def _update_slot(self, slot, idx, work):
        slot['current_work'] = work
        title = work.get("title", "\u65e0\u6807\u9898")

        slot['original_title'] = title
        slot['translated_title'] = ''
        slot['show_translated'] = False
        slot['title_label'].config(text=title)
        slot['title_label']._work_index = idx
        slot['img_label']._work_index = idx
        slot['toggle_btn'].pack_forget()

        raw_tags = [tag["i18n"]["zh-cn"]["name"] for tag in work.get("tags", []) if tag.get("i18n", {}).get("zh-cn")]
        tags = [t for t in raw_tags if t]
        self._draw_tags_on_canvas(slot['tags_label'], tags)

        source_id = work.get('source_id', '')
        slot['id_label'].config(text=f"ID: {source_id}")
        slot['id_label']._work_index = idx

        slot['copy_btn'].config(command=lambda sid=source_id: self.copy_to_clipboard(sid))

        work_id = str(work.get('id', ''))
        cached_translated = self.db.get_translated_title(work_id)
        if cached_translated:
            slot['translated_title'] = cached_translated
            slot['show_translated'] = True
            slot['title_label'].config(text=cached_translated)
            slot['toggle_btn'].config(
                text="原",
                command=lambda s=slot: self._toggle_title(s)
            )
            slot['toggle_btn'].pack(side=tk.LEFT, padx=(3, 0))
            if _config.AI_TRANSLATE_EDITABLE:
                slot['edit_btn'].config(
                    command=lambda s=slot, wid=work_id: self._edit_translation(s, wid)
                )
                slot['edit_btn'].pack(side=tk.LEFT, padx=(2, 0))
            else:
                slot['edit_btn'].pack_forget()
            slot['translate_btn'].pack_forget()
        elif _config.AI_TRANSLATE_ENABLED and _config.AI_API_KEY:
            slot['edit_btn'].pack_forget()
            slot['translate_btn'].config(command=lambda s=slot, t=title, wid=work_id: self._translate_title(s, t, wid))
            slot['translate_btn'].pack(side=tk.LEFT, padx=(3, 0))
        else:
            slot['edit_btn'].pack_forget()
            slot['translate_btn'].pack_forget()

        normalized_id = self._normalize_rj_id(source_id)
        is_downloaded = normalized_id in self.downloaded_ids_cache
        if is_downloaded:
            slot['downloaded_label'].pack(side=tk.LEFT, padx=(10, 0))
        else:
            slot['downloaded_label'].pack_forget()

        colors = getattr(self, 'COLORS', {
            "bg": "#f5f5f5",
            "card_bg": "#ffffff",
            "primary": "#1976D2",
            "primary_light": "#E3F2FD",
            "accent": "#FF9800",
            "success": "#4CAF50",
            "error": "#F44336",
            "text": "#333333",
            "text_secondary": "#666666",
            "text_hint": "#999999",
            "border": "#e0e0e0",
        })

        for w in slot['editions_container'].winfo_children():
            w.destroy()
        other_editions = work.get('other_language_editions_in_db', [])
        for edition in other_editions:
            if edition.get('source_id'):
                lang = edition.get('lang', '')
                ed_id = edition.get('source_id', '')
                ed_label = tk.Label(slot['editions_container'],
                                    text=f"{lang}:{ed_id}", font=("Microsoft YaHei UI", 8),
                                    foreground="#9C27B0", bg=colors["card_bg"], anchor=tk.W, cursor="hand2")
                ed_label.pack(side=tk.LEFT, padx=(2, 0))
                ed_label._edition_sid = ed_id
                ed_label.bind("<Button-1>", self._on_edition_click)

        slot['img_label'].config(image="", text="加载中", bg=colors["border"], fg=colors["text_hint"])
        thumbnail = work.get("thumbnailCoverUrl", "")
        if thumbnail:
            cached = self.image_cache.get(thumbnail)
            if cached:
                slot['img_label'].config(image=cached, text="", bg=colors["border"])
                slot['img_label'].image = cached
                return None
            return thumbnail
        return None

    def _translate_title(self, slot, title, work_id=""):
        translator = get_translator()

        cached = translator.get_cached(title)
        if cached:
            self._apply_translation(slot, title, cached, work_id)
            return

        slot['translate_btn'].config(text="...", state=tk.DISABLED)

        def on_result(translated):
            self.root.after(0, self._on_translate_result, slot, title, translated, work_id)

        translator.translate(title, on_result)

    def _on_translate_result(self, slot, original, translated, work_id=""):
        try:
            if not slot['translate_btn'].winfo_exists():
                return
            if translated:
                self._apply_translation(slot, original, translated, work_id)
                self.status_label.config(text=f"\u2713 \u7ffb\u8bd1\u5b8c\u6210", fg="#4CAF50")
            else:
                slot['translate_btn'].config(text="\u7ffb\u8bd1", state=tk.NORMAL)
                self.status_label.config(text="\u7ffb\u8bd1\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 API \u8bbe\u7f6e\u6216\u7f51\u7edc\u8fde\u63a5", fg="#f44336")
        except Exception:
            pass

    def _apply_translation(self, slot, original, translated, work_id=""):
        slot['original_title'] = original
        slot['translated_title'] = translated
        slot['show_translated'] = True
        slot['title_label'].config(text=translated)
        slot['translate_btn'].pack_forget()
        slot['toggle_btn'].config(
            text="原",
            command=lambda s=slot: self._toggle_title(s)
        )
        slot['toggle_btn'].pack(side=tk.LEFT, padx=(3, 0))
        slot['edit_btn'].config(
            command=lambda s=slot, wid=work_id: self._edit_translation(s, wid)
        )
        slot['edit_btn'].pack(side=tk.LEFT, padx=(2, 0))
        if work_id:
            self.db.save_translated_title(work_id, translated)

    def _toggle_title(self, slot):
        if slot['show_translated']:
            slot['show_translated'] = False
            slot['title_label'].config(text=slot['original_title'])
            slot['toggle_btn'].config(text="译")
        else:
            slot['show_translated'] = True
            slot['title_label'].config(text=slot['translated_title'])
            slot['toggle_btn'].config(text="原")

    def _edit_translation(self, slot, work_id=""):
        current_translated = slot.get('translated_title', '')
        original_title = slot.get('original_title', '')

        edit_win = tk.Toplevel(self.root)
        edit_win.title("编辑翻译")
        edit_win.transient(self.root)
        edit_win.grab_set()

        win_w = 450
        win_h = 200
        screen_w = edit_win.winfo_screenwidth()
        screen_h = edit_win.winfo_screenheight()
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        edit_win.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        edit_win.resizable(False, False)

        main_frame = ttk.Frame(edit_win, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"原文: {original_title[:40]}...",
                 font=("Microsoft YaHei UI", 9), foreground="gray").pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text="翻译:", font=("Microsoft YaHei UI", 10)).pack(anchor=tk.W)
        entry_var = tk.StringVar(value=current_translated)
        entry = ttk.Entry(main_frame, textvariable=entry_var, width=50, font=("Microsoft YaHei UI", 10))
        entry.pack(fill=tk.X, pady=(5, 15))
        entry.select_range(0, tk.END)
        entry.focus_set()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        def save_edit():
            new_translated = entry_var.get().strip()
            if new_translated:
                slot['translated_title'] = new_translated
                if slot['show_translated']:
                    slot['title_label'].config(text=new_translated)
                if work_id:
                    self.db.save_translated_title(work_id, new_translated)
                self.status_label.config(text="✓ 翻译已更新", fg="#4CAF50")
            edit_win.destroy()

        def delete_translation():
            slot['translated_title'] = ''
            slot['show_translated'] = False
            slot['title_label'].config(text=slot['original_title'])
            slot['toggle_btn'].pack_forget()
            slot['edit_btn'].pack_forget()
            slot['translate_btn'].pack(side=tk.LEFT, padx=(3, 0))
            if work_id:
                self.db.delete_translated_title(work_id)
            self.status_label.config(text="✓ 翻译已删除", fg="#FF9800")
            edit_win.destroy()

        ttk.Button(btn_frame, text="保存", command=save_edit).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text="删除翻译", command=delete_translation).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(btn_frame, text="取消", command=edit_win.destroy).pack(side=tk.RIGHT)

        edit_win.bind("<Return>", lambda e: save_edit())
        edit_win.bind("<Escape>", lambda e: edit_win.destroy())

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

        logger.debug("display_works_list 调用 update_idletasks")
        self.root.update_idletasks()
        logger.debug("display_works_list update_idletasks 完成")

        for idx, work in enumerate(self.works):
            slot = self._card_slots[idx]
            thumb_url = self._update_slot(slot, idx, work)
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
        executor = ThreadPoolExecutor(max_workers=8)
        results = []

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

        futures = [executor.submit(load_one, slot, url, idx) for slot, url, idx in items]
        for future in futures:
            result = future.result()
            if result:
                results.append(result)
        executor.shutdown(wait=False)

        if results and getattr(self, '_nav_generation', 0) == gen:
            self.root.after(0, self._batch_update_thumbnails, results)

    def _batch_update_thumbnails(self, results):
        colors = getattr(self, 'COLORS', {
            "border": "#e0e0e0",
        })
        for slot, pil_img, url in results:
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
        tk.Label(empty_frame, text="\u6682\u65e0\u6570\u636e", font=("Microsoft YaHei UI", 14),
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
