import tkinter as tk
from tkinter import font as tkfont
import logging
import time

from .. import config as _config
from ..services.translator import get_translator

logger = logging.getLogger('list_card')

_TAG_FONT = None


def _get_tag_font():
    global _TAG_FONT
    if _TAG_FONT is None:
        _TAG_FONT = tkfont.Font(family="Microsoft YaHei UI", size=9)
    return _TAG_FONT


def _hover_children(widget, from_bg, to_bg):
    try:
        wtype = widget.winfo_class()
    except Exception:
        return
    if wtype in ("Button", "Canvas"):
        return
    if wtype in ("Frame", "Label"):
        try:
            if widget.cget("bg") == from_bg:
                widget.config(bg=to_bg)
        except Exception:
            pass
    for child in widget.winfo_children():
        _hover_children(child, from_bg, to_bg)


class ListCardMixin:
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

        def _on_enter(e, f=frame, c=colors):
            f.config(bg=c["primary_light"])
            for child in f.winfo_children():
                _hover_children(child, c["card_bg"], c["primary_light"])
        def _on_leave(e, f=frame, c=colors):
            f.config(bg=c["card_bg"])
            for child in f.winfo_children():
                _hover_children(child, c["primary_light"], c["card_bg"])
        frame.bind("<Enter>", _on_enter)
        frame.bind("<Leave>", _on_leave)
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

        title_label = tk.Label(title_frame, text="", font=("Segoe UI", 10, "bold"),
                               cursor="hand2", bg=colors["card_bg"], fg=colors["text"], anchor=tk.W, wraplength=420)
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_column = tk.Frame(title_frame, bg=colors["card_bg"])
        btn_column.pack(side=tk.LEFT, padx=(6, 0))

        downloaded_label = tk.Label(btn_column, text="✓ 已下载", bg=colors["primary"], fg="white",
                                     font=("Microsoft YaHei UI", 8, "bold"), padx=6, pady=2)
        downloaded_label.pack(anchor=tk.E, pady=(0, 1))
        downloaded_label.pack_forget()

        toggle_btn = tk.Button(btn_column, text="译", font=("Microsoft YaHei UI", 8),
                               relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                               bg=colors["primary_light"], fg=colors["primary"], width=2)
        toggle_btn.pack(anchor=tk.E, pady=(1, 0))
        toggle_btn.pack_forget()

        edit_btn = tk.Button(btn_column, text="编辑", font=("Microsoft YaHei UI", 8),
                             relief=tk.FLAT, padx=4, pady=1, cursor="hand2",
                             bg="#FFF3E0", fg=colors["accent"], width=3)
        edit_btn.pack(anchor=tk.E, pady=(1, 0))
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
            'btn_column': btn_column,
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
            canvas.update_idletasks()
            cw = canvas.winfo_width()
        if not cw or cw < 50:
            cw = 480
        TAG_COLORS = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#E91E63",
                       "#00BCD4", "#8BC34A", "#FF5722"]
        tag_font = _get_tag_font()
        x, y = 2, 2
        row_height = 26
        max_width = cw - 4
        for idx, tag in enumerate(tags[:12]):
            color = TAG_COLORS[idx % len(TAG_COLORS)]
            tw = tag_font.measure(tag) + 12
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

    def _update_slot(self, slot, idx, work, translations=None):
        slot['current_work'] = work
        title = work.get("title", "无标题")

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
        if translations is not None:
            cached_translated = translations.get(work_id, '')
        else:
            cached_translated = self.db.get_translated_title(work_id)
        if cached_translated:
            slot['translated_title'] = cached_translated
            slot['show_translated'] = True
            slot['title_label'].config(text=cached_translated)
            slot['toggle_btn'].config(
                text="原",
                command=lambda s=slot: self._toggle_title(s)
            )
            slot['toggle_btn'].pack(anchor=tk.E, pady=(1, 0))
            if _config.AI_TRANSLATE_EDITABLE:
                slot['edit_btn'].config(
                    command=lambda s=slot, wid=work_id: self._edit_translation(s, wid)
                )
                slot['edit_btn'].pack(anchor=tk.E, pady=(1, 0))
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
            slot['downloaded_label'].pack(anchor=tk.E, pady=(0, 1))
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
                ed_norm = self._normalize_rj_id(ed_id)
                is_ed_downloaded = ed_norm in self.downloaded_ids_cache
                if is_ed_downloaded:
                    ed_text = f"✓{lang}:{ed_id}"
                    ed_fg = "#2E7D32"
                else:
                    ed_text = f"{lang}:{ed_id}"
                    ed_fg = "#9C27B0"
                ed_label = tk.Label(slot['editions_container'],
                                    text=ed_text, font=("Microsoft YaHei UI", 8),
                                    foreground=ed_fg, bg=colors["card_bg"], anchor=tk.W, cursor="hand2")
                ed_label.pack(side=tk.LEFT, padx=(2, 0))
                ed_label._edition_sid = ed_id
                ed_label.bind("<Button-1>", self._on_edition_click)

        slot['img_label'].config(image="", text="加载中", bg=colors["border"], fg=colors["text_hint"])
        thumbnail = work.get("thumbnailCoverUrl", "")
        if thumbnail:
            cached = self.image_cache.memory_cache.get(f"thumb_{thumbnail}")
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

        current_text = slot['translate_btn'].cget('text')
        if current_text != "翻译":
            return

        slot['translate_btn'].config(text="翻译中.", state=tk.DISABLED,
                                     bg="#FFF3E0", fg="#E65100")
        self._translation_dots = [".", "..", "..."]
        self._translation_dot_index = 0

        # 标记此翻译请求已发出，用于超时检测
        slot['_translation_active'] = True
        slot['_translation_start'] = time.time()

        def animate_dots():
            if not slot['translate_btn'].winfo_exists():
                return
            current = slot['translate_btn'].cget('text')
            if not current.startswith("翻译中"):
                return
            self._translation_dot_index = (self._translation_dot_index + 1) % 3
            slot['translate_btn'].config(text=f"翻译中{self._translation_dots[self._translation_dot_index]}")
            self.root.after(500, animate_dots)

        self.root.after(500, animate_dots)

        # 超时保护：思考模式下推理较慢，超时放宽到 100 秒；普通模式 35 秒
        thinking_enabled = getattr(_config, 'AI_THINKING_ENABLED', True)
        timeout_ms = 100000 if thinking_enabled else 35000

        def on_timeout():
            if not slot.get('_translation_active'):
                return
            if not slot['translate_btn'].winfo_exists():
                return
            current = slot['translate_btn'].cget('text')
            if current.startswith("翻译中"):
                slot['_translation_active'] = False
                colors = getattr(self, 'COLORS', {"card_bg": "#ffffff", "success": "#4CAF50"})
                slot['translate_btn'].config(text="翻译", state=tk.NORMAL,
                                             bg=colors.get("card_bg", "#ffffff"), fg=colors.get("success", "#4CAF50"))
                self.status_label.config(text="翻译超时，请检查网络或 API 设置", foreground="#f44336")
                logger.warning(f"翻译超时: {title[:30]}...")

        timeout_timer = self.root.after(timeout_ms, on_timeout)
        slot['_translation_timeout_timer'] = timeout_timer

        def on_result(translated):
            # 取消超时计时器
            if slot.get('_translation_timeout_timer'):
                try:
                    self.root.after_cancel(slot['_translation_timeout_timer'])
                except Exception:
                    pass
                slot['_translation_timeout_timer'] = None
            slot['_translation_active'] = False
            self.root.after(0, self._on_translate_result, slot, title, translated, work_id)

        translator.translate(title, on_result)

    def _on_translate_result(self, slot, original, translated, work_id=""):
        try:
            if not slot['translate_btn'].winfo_exists():
                return
            if translated:
                self._apply_translation(slot, original, translated, work_id)
                self.status_label.config(text="✓ 翻译完成", foreground="#4CAF50")
            else:
                slot['translate_btn'].config(text="翻译", state=tk.NORMAL)
                self.status_label.config(text="翻译失败，请检查 API 设置或网络连接", foreground="#f44336")
        except Exception as e:
            # 翻译结果处理失败时，恢复按钮状态
            try:
                if slot['translate_btn'].winfo_exists():
                    slot['translate_btn'].config(text="翻译", state=tk.NORMAL)
                self.status_label.config(text=f"翻译处理失败：{str(e)}", foreground="#f44336")
            except Exception:
                pass
            logger.error(f"_on_translate_result 异常：{e}")

    def _apply_translation(self, slot, original, translated, work_id=""):
        try:
            slot['original_title'] = original
            slot['translated_title'] = translated
            slot['show_translated'] = True
            slot['title_label'].config(text=translated)
            slot['translate_btn'].pack_forget()
            slot['toggle_btn'].config(
                text="原",
                command=lambda s=slot: self._toggle_title(s)
            )
            slot['toggle_btn'].pack(anchor=tk.E, pady=(1, 0))
            slot['edit_btn'].config(
                command=lambda s=slot, wid=work_id: self._edit_translation(s, wid)
            )
            slot['edit_btn'].pack(anchor=tk.E, pady=(1, 0))
            if work_id:
                self.db.save_translated_title(work_id, translated)
        except Exception as e:
            # 应用翻译失败时，恢复按钮状态
            try:
                if slot['translate_btn'].winfo_exists():
                    slot['translate_btn'].config(text="翻译", state=tk.NORMAL)
                self.status_label.config(text=f"应用翻译失败：{str(e)}", foreground="#f44336")
            except Exception:
                pass
            logger.error(f"_apply_translation 异常：{e}")

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

        main_frame = tk.Frame(edit_win, bg="#f0f0f0", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text=f"原文: {original_title[:40]}...",
                 font=("Microsoft YaHei UI", 9), fg="gray", bg="#f0f0f0").pack(anchor=tk.W, pady=(0, 10))

        tk.Label(main_frame, text="翻译:", font=("Microsoft YaHei UI", 10), bg="#f0f0f0").pack(anchor=tk.W)
        entry_var = tk.StringVar(value=current_translated)
        entry = tk.Entry(main_frame, textvariable=entry_var, width=50, font=("Microsoft YaHei UI", 10))
        entry.pack(fill=tk.X, pady=(5, 15))
        entry.select_range(0, tk.END)
        entry.focus_set()

        btn_frame = tk.Frame(main_frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X)

        def save_edit():
            new_translated = entry_var.get().strip()
            if new_translated:
                slot['translated_title'] = new_translated
                if slot['show_translated']:
                    slot['title_label'].config(text=new_translated)
                if work_id:
                    self.db.save_translated_title(work_id, new_translated)
                get_translator().invalidate(original_title)
                self.status_label.config(text="✓ 翻译已更新", foreground="#4CAF50")
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
            get_translator().invalidate(original_title)
            self.status_label.config(text="✓ 翻译已删除", foreground="#FF9800")
            edit_win.destroy()

        tk.Button(btn_frame, text="保存", font=("Microsoft YaHei UI", 10),
                  bg="#4CAF50", fg="white", padx=12, command=save_edit).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="删除翻译", font=("Microsoft YaHei UI", 10),
                  bg="#f44336", fg="white", padx=12, command=delete_translation).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="取消", font=("Microsoft YaHei UI", 10),
                  padx=12, command=edit_win.destroy).pack(side=tk.RIGHT)

        edit_win.bind("<Return>", lambda e: save_edit())
        edit_win.bind("<Escape>", lambda e: edit_win.destroy())

    def _refresh_card_download_status(self):
        if not hasattr(self, '_card_slots'):
            return
        for slot in self._card_slots:
            work = slot.get('current_work')
            if not work:
                continue
            source_id = work.get('source_id', '')
            normalized_id = self._normalize_rj_id(source_id)
            is_downloaded = normalized_id in self.downloaded_ids_cache
            try:
                if slot['downloaded_label'].winfo_exists():
                    if is_downloaded:
                        slot['downloaded_label'].pack(anchor=tk.E, pady=(0, 1))
                    else:
                        slot['downloaded_label'].pack_forget()
            except Exception:
                pass