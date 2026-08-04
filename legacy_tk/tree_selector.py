import logging
from tkinter import ttk
from typing import Callable, List

logger = logging.getLogger(__name__)


class TreeSelector:
    """树状图选择操作工具类 - 可独立使用"""

    def __init__(self, tree: ttk.Treeview):
        """
        初始化树状选择器

        Args:
            tree: tkinter Treeview 控件
        """
        self.tree = tree
        self._selection_callbacks: List[Callable] = []

    def select_all(self) -> None:
        """全选所有节点"""
        for item in self.tree.get_children():
            self.tree.selection_add(item)
            self._select_all_children(item)

    def _select_all_children(self, parent: str) -> None:
        """递归全选子节点"""
        for child in self.tree.get_children(parent):
            self.tree.selection_add(child)
            self._select_all_children(child)

    def invert_selection(self) -> None:
        """反选所有节点"""
        all_items = self._collect_all_items()

        selected = set(self.tree.selection())
        self.tree.selection_remove(selected)

        for item in all_items:
            if item not in selected:
                self.tree.selection_add(item)

    def deselect_all(self) -> None:
        """取消所有选中"""
        self.tree.selection_remove(*self.tree.selection())

    def select_all_in_folder(self, folder_id: str) -> None:
        """
        全选指定文件夹内的所有内容

        Args:
            folder_id: 文件夹节点的ID
        """
        self.tree.selection_add(folder_id)
        self._select_all_children(folder_id)

    def deselect_all_in_folder(self, folder_id: str) -> None:
        """
        取消选择指定文件夹内的所有内容

        Args:
            folder_id: 文件夹节点的ID
        """
        for child in self.tree.get_children(folder_id):
            self.tree.selection_remove(child)
            self._deselect_all_children(child)

    def _deselect_all_children(self, parent: str) -> None:
        """递归取消选择所有子节点"""
        for child in self.tree.get_children(parent):
            self.tree.selection_remove(child)
            self._deselect_all_children(child)

    def get_selected_items(self) -> List[str]:
        """
        获取所有选中的项目ID列表

        Returns:
            选中的节点ID列表
        """
        return list(self.tree.selection())

    def get_selected_leaf_items(self) -> List[str]:
        """
        获取所有选中的叶子节点（文件）

        Returns:
            选中的叶子节点ID列表
        """
        selected = []
        for item_id in self.tree.selection():
            if not self.tree.get_children(item_id):
                selected.append(item_id)
        return selected

    def get_selected_folders(self) -> List[str]:
        """
        获取所有选中的文件夹节点

        Returns:
            选中的文件夹节点ID列表
        """
        selected = []
        for item_id in self.tree.selection():
            if self.tree.get_children(item_id):
                selected.append(item_id)
        return selected

    def get_item_path(self, item_id: str, separator: str = "/") -> str:
        """
        获取节点的完整路径

        Args:
            item_id: 节点ID
            separator: 路径分隔符

        Returns:
            从根到该节点的完整路径
        """
        path_parts = []
        current = item_id

        while current:
            path_parts.insert(0, self.tree.item(current, "text"))
            parent = self.tree.parent(current)
            current = parent if parent else None

        return separator.join(path_parts)

    def get_item_depth(self, item_id: str) -> int:
        """
        获取节点的深度（根节点为0）

        Args:
            item_id: 节点ID

        Returns:
            节点深度
        """
        depth = 0
        current = self.tree.parent(item_id)

        while current:
            depth += 1
            current = self.tree.parent(current)

        return depth

    def expand_all(self) -> None:
        """展开所有节点"""
        for item in self.tree.get_children():
            self._expand_item_and_children(item)

    def collapse_all(self) -> None:
        """折叠所有节点"""
        for item in self.tree.get_children():
            self._collapse_item_and_children(item)

    def _expand_item_and_children(self, item_id: str) -> None:
        """递归展开节点及其子节点"""
        self.tree.item(item_id, open=True)
        for child in self.tree.get_children(item_id):
            self._expand_item_and_children(child)

    def _collapse_item_and_children(self, item_id: str) -> None:
        """递归折叠节点及其子节点"""
        self.tree.item(item_id, open=False)
        for child in self.tree.get_children(item_id):
            self._collapse_item_and_children(child)

    def _collect_all_items(self, parent: str = "") -> List[str]:
        """收集所有节点ID"""
        all_items = []
        for item in self.tree.get_children(parent):
            all_items.append(item)
            all_items.extend(self._collect_all_items(item))
        return all_items

    def get_items_by_type(self, item_type: str) -> List[str]:
        """
        根据类型获取节点（需要配合自定义数据使用）

        Args:
            item_type: 节点类型标识

        Returns:
            指定类型的节点ID列表
        """
        items = []
        for item_id in self._collect_all_items():
            values = self.tree.item(item_id, "values")
            if values and len(values) > 1 and values[1] == item_type:
                items.append(item_id)
        return items

    def register_selection_callback(self, callback: Callable[[List[str]], None]) -> None:
        """
        注册选中状态变化回调函数

        Args:
            callback: 回调函数，参数为选中的节点ID列表
        """
        self._selection_callbacks.append(callback)

    def notify_selection_changed(self) -> None:
        """通知所有注册回调函数选中状态已变化"""
        selected = self.get_selected_items()
        for callback in self._selection_callbacks:
            try:
                callback(selected)
            except Exception:
                logger.debug("选择回调执行异常", exc_info=True)

    def print_tree_structure(self, parent: str = "", level: int = 0) -> None:
        """
        打印树结构（调试用）

        Args:
            parent: 父节点ID
            level: 当前层级
        """
        indent = "  " * level
        for item in self.tree.get_children(parent):
            text = self.tree.item(item, "text")
            values = self.tree.item(item, "values")
            has_children = bool(self.tree.get_children(item))
            marker = "[+]" if has_children else ""
            logger.debug("%s%s%s %s", indent, marker, text, values if values else "")
            self.print_tree_structure(item, level + 1)
