import tkinter as tk
from tkinter import messagebox
import threading

from ..api_client import get_api_client


class DetailActionsMixin:
    def hide_current_work(self):
        if self.current_work_index < 0 or self.current_work_index >= len(self.works):
            return
        work = self.works[self.current_work_index]
        work_id = str(work.get("id", ""))
        self.db.hide_work(work_id)
        self.status_label.config(text=f"✓ 已隐藏: {work.get('title', '')[:20]}...")
        next_index = self.current_work_index
        del self.works[self.current_work_index]
        if self.works:
            if next_index >= len(self.works):
                next_index = len(self.works) - 1
            self.display_works_list()
            self.show_work_detail(next_index)
        else:
            self.display_empty_state()
            self.show_work_detail(-1)

    def _refresh_work_detail(self):
        if self.current_work_index < 0 or self.current_work_index >= len(self.works):
            return
        work = self.works[self.current_work_index]
        source_id = work.get("source_id", "")
        if not source_id:
            return

        self.refresh_detail_btn.config(state=tk.DISABLED, text="刷新中...")
        self.status_label.config(text="正在重新获取作品信息...")
        threading.Thread(target=self._refresh_work_detail_async, args=(self.current_work_index, source_id), daemon=True).start()

    def _refresh_work_detail_async(self, index, source_id):
        try:
            api_client = get_api_client()
            data = api_client.fetch_work_detail(source_id)
            self.root.after(0, self._on_refresh_complete, index, data)
        except Exception as e:
            self.root.after(0, self._on_refresh_error, str(e))

    def _on_refresh_complete(self, index, data):
        if index != self.current_work_index or index >= len(self.works):
            return

        work = self.works[index]
        work["title"] = data.get("title", work.get("title", ""))
        work["thumbnailCoverUrl"] = data.get("thumbnailCoverUrl", "")
        work["mainCoverUrl"] = data.get("mainCoverUrl", "")
        work["tags"] = data.get("tags", [])
        work["vas"] = data.get("vas", [])
        work["circle"] = data.get("circle", {})
        work["other_language_editions_in_db"] = data.get("other_language_editions_in_db", [])

        if self.current_tab == "recommend":
            self.db.update_works_cache(work, self.current_page)

        source_id = work.get("source_id", "")
        normalized = self._normalize_rj_id(source_id)
        if normalized in self.downloaded_ids_cache:
            tags = [tag["i18n"]["zh-cn"]["name"] for tag in data.get("tags", []) if tag.get("i18n", {}).get("zh-cn")]
            tags = [t for t in tags if t] or None
            self.download_history.update_work_detail(
                f"RJ{normalized}",
                thumbnail_url=data.get("thumbnailCoverUrl") or None,
                main_cover_url=data.get("mainCoverUrl") or None,
                tags=tags,
                vas=data.get("vas", []) or None,
                circle_data=data.get("circle", {}) or None,
                other_editions=data.get("other_language_editions_in_db", []) or None
            )

        self.refresh_detail_btn.config(state=tk.NORMAL, text="刷新信息")
        self.status_label.config(text="✓ 作品信息已刷新")
        self.show_work_detail(index)
        self.display_works_list()

    def _on_refresh_error(self, msg):
        self.refresh_detail_btn.config(state=tk.NORMAL, text="刷新信息")
        self.status_label.config(text="")
        messagebox.showerror("刷新失败", f"获取作品信息失败: {msg}")

    def _delete_download_record(self):
        if self.current_work_index < 0 or self.current_work_index >= len(self.works):
            return
        work = self.works[self.current_work_index]
        source_id = work.get("source_id", "")
        if not source_id:
            return

        title = work.get("title", "未知作品")
        if not messagebox.askyesno("确认删除", f"确定要删除「{title[:30]}」的下载记录吗？\n（仅删除数据库记录，不影响已下载的文件）"):
            return

        db_rj_id = f"RJ{self._normalize_rj_id(source_id)}"
        self.download_history.delete_download(db_rj_id)

        normalized = self._normalize_rj_id(source_id)
        self.downloaded_ids_cache.discard(normalized)
        self._update_downloaded_count()

        if hasattr(self, '_all_downloaded_works') and self._all_downloaded_works:
            self._all_downloaded_works = [
                w for w in self._all_downloaded_works
                if self._normalize_rj_id(w.get("source_id", "")) != normalized
            ]
        if hasattr(self, 'downloaded_works_cache') and self.downloaded_works_cache:
            self.downloaded_works_cache = [
                w for w in self.downloaded_works_cache
                if self._normalize_rj_id(w.get("source_id", "")) != normalized
            ]

        self.status_label.config(text=f"✓ 已删除下载记录: {title[:20]}...")
        if self.show_downloaded == 3:
            if self.works:
                next_idx = self.current_work_index
                del self.works[self.current_work_index]
                if self.works:
                    if next_idx >= len(self.works):
                        next_idx = len(self.works) - 1
                    self.display_works_list()
                    self.show_work_detail(next_idx)
                else:
                    self.display_empty_state()
                    self.show_work_detail(-1)
        else:
            self.display_works_list()
            self.show_work_detail(self.current_work_index)

    def _toggle_detail_title(self):
        if self._detail_show_translated:
            self._detail_show_translated = False
            self.info_labels["title"].config(text=self._detail_original_title)
            self.detail_toggle_btn.config(text="译")
        else:
            self._detail_show_translated = True
            self.info_labels["title"].config(text=self._detail_translated_title)
            self.detail_toggle_btn.config(text="原")

    def _copy_detail_title(self):
        if self._detail_show_translated and self._detail_translated_title:
            text = self._detail_translated_title
        else:
            text = self._detail_original_title
        self.copy_to_clipboard(text)

    def _copy_detail_id(self):
        if self.current_work_index < 0 or self.current_work_index >= len(self.works):
            return
        work = self.works[self.current_work_index]
        source_id = work.get("source_id", "")
        if source_id:
            self.copy_to_clipboard(source_id)