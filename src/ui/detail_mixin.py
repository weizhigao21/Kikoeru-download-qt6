import tkinter as tk
from tkinter import ttk
import threading
import logging

from PIL import ImageTk

from ..api_client import get_api_client
from .detail_actions import DetailActionsMixin
from .fonts import DEFAULT, SMALL, TINY, BODY, LABEL, EMOJI

logger = logging.getLogger('detail_mixin')


class DetailMixin(DetailActionsMixin):
    def setup_detail_panel(self):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

        self.detail_canvas = tk.Canvas(self.detail_frame, bg="#f0f0f0", highlightthickness=0)
        self.detail_scrollbar = ttk.Scrollbar(self.detail_frame, orient=tk.VERTICAL, command=self.detail_canvas.yview)
        self.detail_scrollable = tk.Frame(self.detail_canvas, bg="#f0f0f0")

        self.detail_scrollable.bind(
            "<Configure>",
            lambda e: self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))
        )

        self.detail_canvas_window = self.detail_canvas.create_window((0, 0), window=self.detail_scrollable, anchor="nw", width=380)
        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)

        self.detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.detail_canvas.bind(
            "<Configure>",
            lambda e: self.detail_canvas.itemconfig(
                self.detail_canvas_window,
                width=e.width - self.detail_scrollbar.winfo_width()
            )
        )

        ttk.Label(self.detail_scrollable, text="标题:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self._detail_original_title = ""
        self._detail_translated_title = ""
        self._detail_show_translated = False

        detail_title_frame = tk.Frame(self.detail_scrollable, bg="#f0f0f0")
        detail_title_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 10))

        self.info_labels["title"] = ttk.Label(
            detail_title_frame, text="", font=BODY, wraplength=320, justify=tk.LEFT
        )
        self.info_labels["title"].pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.detail_toggle_btn = tk.Button(detail_title_frame, text="译", font=TINY,
                                           relief=tk.FLAT, padx=3, pady=1, cursor="hand2",
                                           bg="#E3F2FD", fg="#1976D2", width=2,
                                           command=self._toggle_detail_title)
        self.detail_toggle_btn.pack(side=tk.LEFT, padx=(3, 0))
        self.detail_toggle_btn.pack_forget()

        self.detail_copy_title_btn = tk.Button(detail_title_frame, text="📋", font=EMOJI,
                                               relief=tk.FLAT, padx=3, pady=1, cursor="hand2",
                                               bg="#f0f0f0", fg="#666666",
                                               command=self._copy_detail_title)
        self.detail_copy_title_btn.pack(side=tk.LEFT, padx=(3, 0))

        ttk.Label(self.detail_scrollable, text="封面:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self.image_frame = tk.Frame(self.detail_scrollable, background="#e0e0e0")
        self.image_frame.pack(anchor=tk.W, pady=(0, 10))
        self.image_label = tk.Label(self.image_frame, background="#e0e0e0")
        self.image_label.pack()

        ttk.Label(self.detail_scrollable, text="标签:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self.tags_frame = ttk.Frame(self.detail_scrollable)
        self.tags_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 10))
        self.detail_tags_canvas = tk.Canvas(self.tags_frame, bg="#f0f0f0", height=22, highlightthickness=0)
        self.detail_tags_canvas.pack(anchor=tk.W, fill=tk.X)
        self.detail_tags_canvas._tag_data = []

        ttk.Label(self.detail_scrollable, text="ID:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        detail_id_frame = tk.Frame(self.detail_scrollable, bg="#f0f0f0")
        detail_id_frame.pack(anchor=tk.W, pady=(0, 5))
        self.info_labels["id"] = ttk.Label(detail_id_frame, text="", font=DEFAULT, foreground="blue")
        self.info_labels["id"].pack(side=tk.LEFT)
        self.detail_copy_id_btn = tk.Button(detail_id_frame, text="📋", font=EMOJI,
                                            relief=tk.FLAT, padx=3, pady=1, cursor="hand2",
                                            bg="#f0f0f0", fg="#666666",
                                            command=self._copy_detail_id)
        self.detail_copy_id_btn.pack(side=tk.LEFT, padx=(3, 0))

        ttk.Label(self.detail_scrollable, text="厂商:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self.info_labels["circle"] = tk.Label(
            self.detail_scrollable, text="", font=DEFAULT,
            fg="#2196F3", bg="#f0f0f0", cursor="hand2", anchor=tk.W, wraplength=360, justify=tk.LEFT
        )
        self.info_labels["circle"].pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(self.detail_scrollable, text="声优:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self.info_labels["cv"] = ttk.Label(
            self.detail_scrollable, text="", font=DEFAULT, wraplength=360, justify=tk.LEFT
        )
        self.info_labels["cv"].pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(self.detail_scrollable, text="其他语言版本:", font=LABEL).pack(anchor=tk.W, pady=(0, 2))
        self.info_labels["editions"] = ttk.Label(
            self.detail_scrollable, text="", font=DEFAULT, wraplength=360, justify=tk.LEFT, foreground="gray"
        )
        self.info_labels["editions"].pack(anchor=tk.W)

        self.delete_btn = ttk.Button(self.detail_scrollable, text="隐藏此作品", command=self.hide_current_work)
        self.delete_btn.pack(anchor=tk.W, pady=(15, 0))

        self.refresh_detail_btn = ttk.Button(self.detail_scrollable, text="刷新信息", command=self._refresh_work_detail)
        self.refresh_detail_btn.pack(anchor=tk.W, pady=(5, 0))

        self.delete_download_btn = ttk.Button(self.detail_scrollable, text="删除下载记录", command=self._delete_download_record)
        self.delete_download_btn.pack(anchor=tk.W, pady=(5, 10))
        self.delete_download_btn.pack_forget()

    def _update_detail_tags(self, tags):
        self._draw_tags_on_canvas(self.detail_tags_canvas, tags)

    def show_work_detail(self, index):
        logger.debug("show_work_detail(%s) 开始, works=%s", index, len(self.works) if self.works else 0)
        if index < 0 or index >= len(self.works) or not self.data_loaded:
            return

        self.current_work_index = index
        work = self.works[index]

        title = work.get("title", "无标题")
        self._detail_original_title = title
        self._detail_translated_title = ""
        self._detail_show_translated = False

        work_id = str(work.get("id", ""))
        if work_id:
            cached_translated = self.db.get_translated_title(work_id)
            if cached_translated:
                self._detail_translated_title = cached_translated
                self._detail_show_translated = True
                self.info_labels["title"].config(text=cached_translated)
                self.detail_toggle_btn.config(text="原")
                self.detail_toggle_btn.pack(side=tk.LEFT, padx=(3, 0))
            else:
                self.info_labels["title"].config(text=title)
                self.detail_toggle_btn.pack_forget()
        else:
            self.info_labels["title"].config(text=title)
            self.detail_toggle_btn.pack_forget()

        self.info_labels["id"].config(text=f"ID: {work.get('source_id', '')}")

        circle = work.get("circle", {})
        circle_name = circle.get("name", "") if isinstance(circle, dict) else ""
        self.info_labels["circle"].config(text=circle_name if circle_name else "  无厂商信息")
        if circle_name:
            self.info_labels["circle"].bind("<Button-1>", lambda e, cn=circle_name: self.search_by_circle(cn))
        else:
            self.info_labels["circle"].unbind("<Button-1>")

        vas = work.get("vas", [])
        if vas:
            cv_names = ", ".join([va.get("name", "") for va in vas if va.get("name")])
            self.info_labels["cv"].config(text=cv_names)
        else:
            self.info_labels["cv"].config(text="  无声优信息")

        tags = [tag["i18n"]["zh-cn"]["name"] for tag in work.get("tags", []) if tag.get("i18n", {}).get("zh-cn")]
        tags = [t for t in tags if t]
        self._update_detail_tags(tags)
        logger.debug("show_work_detail 标签完成")

        thumbnail = work.get("mainCoverUrl", "") or work.get("thumbnailCoverUrl", "")
        if thumbnail:
            detail_size = (400, 400)
            logger.debug("show_work_detail 查询图片缓存")
            cached_detail = self.image_cache.get_at_size(thumbnail, detail_size)
            logger.debug("show_work_detail 图片缓存查询完成")
            if cached_detail:
                self.image_label.config(image=cached_detail, text="")
                self.image_label.image = cached_detail
            else:
                cached_thumb = self.image_cache.get(thumbnail)
                if cached_thumb:
                    self.image_label.config(image=cached_thumb, text="")
                    self.image_label.image = cached_thumb
                else:
                    self.image_label.config(image="", text="加载中...")
                self.image_frame.config(background="#e0e0e0")
                threading.Thread(target=self._load_detail_image, args=(thumbnail,), daemon=True).start()
        else:
            self.image_label.config(image="", text="无封面")
            self.image_frame.config(background="#e0e0e0")
        logger.debug("show_work_detail 图片完成")

        other_editions = work.get("other_language_editions_in_db", [])
        if other_editions:
            editions_text = "\n".join([
                f"  [{edition.get('lang', '')}] {edition.get('title', '')} (ID: {edition.get('source_id', '')})"
                for edition in other_editions
            ])
            self.info_labels["editions"].config(text=editions_text)
        else:
            self.info_labels["editions"].config(text="  无其他语言版本")

        circle = work.get("circle", {})
        has_circle = isinstance(circle, dict) and circle.get("name")
        has_vas = bool(work.get("vas", []))
        if not has_circle or not has_vas:
            source_id = work.get("source_id", "")
            if source_id:
                db_work = self._lookup_cached_detail(source_id)
                if db_work:
                    if not has_vas and db_work.get("vas"):
                        work["vas"] = db_work["vas"]
                        has_vas = True
                        cv_names = ", ".join([va.get("name", "") for va in db_work["vas"] if va.get("name")])
                        self.info_labels["cv"].config(text=cv_names)
                    if not has_circle and db_work.get("circle"):
                        work["circle"] = db_work["circle"]
                        has_circle = True
                        cn = db_work["circle"].get("name", "") if isinstance(db_work["circle"], dict) else ""
                        if cn:
                            self.info_labels["circle"].config(text=cn)
                            self.info_labels["circle"].bind("<Button-1>", lambda e, name=cn: self.search_by_circle(name))
                    self.db.update_works_cache(work, self.current_page)
                if not has_circle or not has_vas:
                    self._schedule_lazy_load(index, source_id)

        self.update_buttons()

        source_id = work.get("source_id", "")
        normalized = self._normalize_rj_id(source_id)
        if normalized in self.downloaded_ids_cache:
            self.delete_download_btn.pack(anchor=tk.W, pady=(5, 10))
        else:
            self.delete_download_btn.pack_forget()
        logger.debug("show_work_detail(%s) 完成", index)

    def _schedule_lazy_load(self, index, source_id):
        lazy_gen = getattr(self, '_lazy_generation', 0)
        self._lazy_generation = lazy_gen + 1
        gen = self._lazy_generation
        self.root.after(300, self._do_lazy_load_if_still, index, source_id, gen)

    def _lookup_cached_detail(self, source_id):
        rj_id = self._normalize_rj_id(source_id)
        if not rj_id:
            return None
        full_id = f"RJ{rj_id}"
        result = self.db.get_work_detail_cached(full_id)
        if result:
            return result
        if self.download_history.is_downloaded(full_id):
            rows = self.download_history.get_all_downloaded_works_full()
            for row in rows:
                if self._normalize_rj_id(row.get("id", "")) == rj_id:
                    vas = row.get("vas", [])
                    circle = row.get("circle", {})
                    if vas or (circle and isinstance(circle, dict) and circle.get("name")):
                        return {"vas": vas, "circle": circle}
        return None

    def _do_lazy_load_if_still(self, index, source_id, gen):
        if getattr(self, '_lazy_generation', 0) != gen:
            return
        if index != self.current_work_index:
            return
        threading.Thread(target=self._lazy_load_work_detail, args=(index, source_id), daemon=True).start()

    def _load_detail_image(self, url):
        logger.debug("_load_detail_image 后台线程开始 %s", url[:60])
        try:
            pil_img = self.image_cache._load_pil_from_url(url, (400, 400))
            logger.debug("_load_detail_image 加载完成: %s", pil_img is not None)
            if pil_img:
                self.root.after(0, self._update_detail_image, pil_img, id(self.works))
        except Exception as e:
            logger.debug("_load_detail_image 异常: %s", e)
            self.root.after(0, self._update_detail_image_error)

    def _update_detail_image(self, pil_img, works_id):
        logger.debug("_update_detail_image 主线程执行, works_id=%s", works_id)
        try:
            if id(self.works) != works_id:
                return
            if self.image_label.winfo_exists():
                photo = ImageTk.PhotoImage(pil_img)
                self.image_label.config(image=photo, text="")
                self.image_label.image = photo
                self.image_frame.config(background="#333333")
        except Exception:
            pass

    def _update_detail_image_error(self):
        try:
            if self.image_label.winfo_exists():
                self.image_label.config(image="", text="加载失败")
        except Exception:
            pass

    def _lazy_load_work_detail(self, index, source_id):
        try:
            api_client = get_api_client()
            data = api_client.fetch_work_detail(source_id)
            vas = data.get("vas", [])
            circle = data.get("circle", {})
            main_cover_url = data.get("mainCoverUrl", "")
            self.root.after(0, self._on_lazy_detail_loaded, index, vas, circle, main_cover_url)

            normalized = self._normalize_rj_id(source_id)
            if normalized and normalized in self.downloaded_ids_cache:
                tags = [tag["i18n"]["zh-cn"]["name"] for tag in data.get("tags", []) if tag.get("i18n", {}).get("zh-cn")]
                tags = [t for t in tags if t]
                self.download_history.update_work_detail(
                    f"RJ{normalized}",
                    thumbnail_url=data.get("thumbnailCoverUrl") or None,
                    main_cover_url=data.get("mainCoverUrl") or None,
                    tags=tags or None,
                    vas=vas or None,
                    circle_data=circle or None,
                    other_editions=data.get("other_language_editions_in_db", []) or None
                )
        except Exception:
            pass

    def _on_lazy_detail_loaded(self, index, vas, circle, main_cover_url=""):
        if index != self.current_work_index or index >= len(self.works):
            return
        work = self.works[index]
        work["vas"] = vas
        work["circle"] = circle
        if main_cover_url:
            work["mainCoverUrl"] = main_cover_url
            current_thumb = work.get("thumbnailCoverUrl", "")
            if main_cover_url != current_thumb:
                detail_size = (400, 400)
                cached_detail = self.image_cache.get_at_size(main_cover_url, detail_size)
                if cached_detail:
                    self.image_label.config(image=cached_detail, text="")
                    self.image_label.image = cached_detail
                else:
                    threading.Thread(target=self._load_detail_image, args=(main_cover_url,), daemon=True).start()
        if vas:
            cv_names = ", ".join([va.get("name", "") for va in vas if va.get("name")])
            self.info_labels["cv"].config(text=cv_names)
        circle_name = circle.get("name", "") if isinstance(circle, dict) else ""
        if circle_name:
            self.info_labels["circle"].config(text=circle_name)
            self.info_labels["circle"].bind("<Button-1>", lambda e, cn=circle_name: self.search_by_circle(cn))
        self.db.update_works_cache(work, self.current_page)