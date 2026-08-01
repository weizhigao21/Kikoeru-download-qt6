import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import logging

from ..api_client import get_api_client
from ..download.manager import DownloadManager
from .tree_selector import TreeSelector

logger = logging.getLogger(__name__)


class DownloadWindow:
    ICON_FOLDER = "\U0001F4C1"
    ICON_AUDIO = "\U0001F3B5"
    ICON_IMAGE = "\U0001F5BC\uFE0F"
    ICON_TEXT = "\U0001F4C4"
    ICON_UNKNOWN = "\U0001F4E6"

    def __init__(self, parent, work, downloaded_ids_cache=None, display_title=None):
        self.parent = parent
        self.work = work
        self.display_title = display_title
        self.downloaded_ids_cache = downloaded_ids_cache
        self.download_tasks = {}
        self.tracks_data = None
        self.item_folder_path = {}
        self._updating_selection = False
        self._prev_selection = set()

        source_id = work.get("source_id", "")
        show_title = display_title if display_title else work.get('title', source_id)
        self.window = tk.Toplevel(parent)
        self.window.title(f"下载 - {show_title[:30]}...")
        self.window.transient(parent)
        self.window.grab_set()

        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        win_w = 700
        win_h = 600
        pos_x = parent_x + (parent_w - win_w) // 2
        pos_y = parent_y + (parent_h - win_h) // 2
        self.window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")

        style = ttk.Style(self.window)
        style.map("Treeview", background=[("selected", "#0078D7")], foreground=[("selected", "white")])
        style.configure("Download.TButton", font=("Microsoft YaHei UI", 10),
                        background="#1976D2", foreground="white")
        style.map("Download.TButton",
                  background=[("active", "#1565C0"), ("disabled", "#cccccc")],
                  foreground=[("active", "white"), ("disabled", "#999999")])

        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.status_label = ttk.Label(main_frame, text="正在加载文件列表...", font=("Microsoft YaHei UI", 10))
        self.status_label.pack(pady=(0, 10))

        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        self.select_all_btn = ttk.Button(toolbar, text="全选", command=self.select_all)
        self.select_all_btn.pack(side=tk.LEFT, padx=5)

        self.select_none_btn = ttk.Button(toolbar, text="取消全选", command=self.select_none)
        self.select_none_btn.pack(side=tk.LEFT, padx=5)

        self.download_btn = ttk.Button(toolbar, text="下载选中", command=self.start_download,
                                       style="Download.TButton")
        self.download_btn.pack(side=tk.LEFT, padx=5)

        self.progress_label = tk.Label(toolbar, text="", font=("Microsoft YaHei UI", 9), bg="#f0f0f0")
        self.progress_label.pack(side=tk.LEFT, padx=10)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, selectmode="extended")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree_selector = TreeSelector(self.tree)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-Button-1>", self.on_double_click)

        threading.Thread(target=self.load_tracks, daemon=True).start()

    def load_tracks(self):
        source_id = self.work.get("source_id", "")
        if not source_id:
            return

        t0 = time.time()
        try:
            api_client = get_api_client()
            self.tracks_data = api_client.fetch_tracks(source_id)
            logger.info("fetch_tracks 耗时 %.1fs (source_id=%s)", time.time() - t0, source_id)
            self.window.after(0, self.display_tree)
        except Exception as e:
            logger.warning("fetch_tracks 失败 %.1fs: %s", time.time() - t0, e)
            self.window.after(0, self.show_error, f"加载失败: {str(e)}")

    def display_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.status_label.config(text="文件列表加载完成")

        if not self.tracks_data:
            return

        if isinstance(self.tracks_data, list):
            for node in self.tracks_data:
                self.process_node("", node, None)
        else:
            self.process_node("", self.tracks_data, None)

    def process_node(self, parent_id, node, tree_parent, current_path=""):
        node_type = node.get("type", "")
        title = node.get("title", "")
        parent = tree_parent if tree_parent else ""

        if node_type == "folder":
            folder_id = self.tree.insert(parent, "end", text=f"{self.ICON_FOLDER} {title}", values=["folder"])
            folder_path = current_path + title + "/"
            self.item_folder_path[folder_id] = folder_path
            children = node.get("children", [])
            for child in children:
                self.process_node(folder_id, child, folder_id, folder_path)
        elif node_type == "audio":
            duration = node.get("duration", 0)
            size = node.get("size", 0)
            size_str = self.format_size(size)
            duration_str = self.format_duration(duration)
            item_id = self.tree.insert(parent, "end", text=f"{self.ICON_AUDIO} {title}", values=["audio", size_str, duration_str])
            self.download_tasks[item_id] = node
            self.item_folder_path[item_id] = current_path
        elif node_type == "image":
            size = node.get("size", 0)
            size_str = self.format_size(size)
            item_id = self.tree.insert(parent, "end", text=f"{self.ICON_IMAGE} {title}", values=["image", size_str, ""])
            self.download_tasks[item_id] = node
            self.item_folder_path[item_id] = current_path
        elif node_type == "text":
            size = node.get("size", 0)
            size_str = self.format_size(size)
            item_id = self.tree.insert(parent, "end", text=f"{self.ICON_TEXT} {title}", values=["text", size_str, ""])
            self.download_tasks[item_id] = node
            self.item_folder_path[item_id] = current_path
        else:
            item_id = self.tree.insert(parent, "end", text=f"{self.ICON_UNKNOWN} {title}", values=["unknown"])
            children = node.get("children", [])
            for child in children:
                self.process_node(item_id, child, item_id, current_path)

    def format_size(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def format_duration(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}小时{mins}分"

    def on_select(self, event):
        if self._updating_selection:
            return
        self._updating_selection = True
        try:
            current = set(self.tree.selection())
            newly_selected = current - self._prev_selection
            newly_deselected = self._prev_selection - current

            for item_id in newly_deselected:
                if self.tree.get_children(item_id):
                    self.tree_selector.deselect_all_in_folder(item_id)

            for item_id in newly_selected:
                if self.tree.get_children(item_id):
                    self.tree_selector.select_all_in_folder(item_id)

            self._prev_selection = set(self.tree.selection())

            leaf_count = sum(1 for i in self._prev_selection if not self.tree.get_children(i))
            self.progress_label.config(text=f"已选择: {leaf_count} 个文件")
        finally:
            self._updating_selection = False

    def select_all(self):
        self._updating_selection = True
        try:
            self.tree_selector.select_all()
            self._prev_selection = set(self.tree.selection())
            leaf_count = sum(1 for i in self._prev_selection if not self.tree.get_children(i))
            self.progress_label.config(text=f"已选择: {leaf_count} 个文件")
        finally:
            self._updating_selection = False

    def select_none(self):
        self._updating_selection = True
        try:
            self.tree_selector.deselect_all()
            self._prev_selection = set()
            self.progress_label.config(text="已选择: 0 个文件")
        finally:
            self._updating_selection = False

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        values = self.tree.item(item_id, "values")
        if values and values[0] == "folder":
            self._updating_selection = True
            try:
                self.tree_selector.select_all_in_folder(item_id)
                self._prev_selection = set(self.tree.selection())
                leaf_count = sum(1 for i in self._prev_selection if not self.tree.get_children(i))
                self.progress_label.config(text=f"已选择: {leaf_count} 个文件")
            finally:
                self._updating_selection = False

    def start_download(self):
        selected = self.tree_selector.get_selected_leaf_items()
        if not selected:
            messagebox.showwarning("提示", "请选择要下载的文件")
            return

        files = []
        for item_id in selected:
            if item_id in self.download_tasks:
                node = self.download_tasks[item_id]
                url = node.get("mediaDownloadUrl") or node.get("mediaStreamUrl")
                if url:
                    files.append({
                        "url": url,
                        "filename": node.get("title", "未命名"),
                        "subfolder": self.item_folder_path.get(item_id, ""),
                    })

        if not files:
            messagebox.showwarning("提示", "未找到可下载的文件链接")
            return

        source_id = self.work.get("source_id", "")
        if source_id and self.downloaded_ids_cache is not None:
            normalized = self._normalize_rj_id(source_id)
            self.downloaded_ids_cache.add(normalized)

        submit_work = dict(self.work)
        if self.display_title:
            submit_work["title"] = self.display_title

        manager = DownloadManager()
        manager.submit(submit_work, files)

        self.status_label.config(text=f"\u2713 已提交 {len(files)} 个文件到下载队列")
        self.progress_label.config(text="")
        self.download_btn.config(state=tk.DISABLED, text="已提交")

        self.window.after(2000, self._auto_close)

    def _auto_close(self):
        try:
            self.window.grab_release()
            self.window.destroy()
        except Exception:
            pass

    def _normalize_rj_id(self, rj_id):
        if not rj_id:
            return ""
        return str(rj_id).replace("RJ", "").replace("rg", "").replace("RG", "").strip().zfill(6)

    def show_error(self, msg):
        self.status_label.config(text=msg, foreground="red")
        messagebox.showerror("错误", msg)
