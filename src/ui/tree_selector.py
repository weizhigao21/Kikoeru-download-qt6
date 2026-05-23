import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Any


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
                pass

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
            print(f"{indent}{marker}{text} {values if values else ''}")
            self.print_tree_structure(item, level + 1)


class TreeBuilder:
    """树状图构建工具类 - 从API数据构建树状结构"""

    @staticmethod
    def build_from_api_data(tree: ttk.Treeview, data: List[dict],
                           text_key: str = "title",
                           type_key: str = "type",
                           children_key: str = "children",
                           parent: str = "") -> None:
        """
        从API数据构建树状图

        Args:
            tree: Treeview控件
            data: API返回的树状数据列表
            text_key: 节点文本的key
            type_key: 节点类型的key
            children_key: 子节点列表的key
            parent: 父节点ID
        """
        for item in data:
            name = item.get(text_key, "未知")
            node_type = item.get(type_key, "file")

            node = tree.insert(parent, tk.END, text=name, values=(node_type,))

            if node_type == "folder" and children_key in item:
                TreeBuilder.build_from_api_data(
                    tree,
                    item[children_key],
                    text_key,
                    type_key,
                    children_key,
                    node
                )

    @staticmethod
    def find_node_by_name(tree: ttk.Treeview, name: str,
                         parent: str = "") -> Optional[str]:
        """
        根据名称查找节点

        Args:
            tree: Treeview控件
            name: 要查找的节点名称
            parent: 父节点ID

        Returns:
            找到的节点ID，未找到返回None
        """
        for item in tree.get_children(parent):
            if tree.item(item, "text") == name:
                return item

            result = TreeBuilder.find_node_by_name(tree, name, item)
            if result:
                return result

        return None

    @staticmethod
    def get_node_data(tree: ttk.Treeview, node_id: str,
                     data: List[dict], text_key: str = "title") -> Optional[dict]:
        """
        根据节点ID获取对应的原始数据

        Args:
            tree: Treeview控件
            node_id: 节点ID
            data: 原始数据列表
            text_key: 节点文本的key

        Returns:
            对应的原始数据字典
        """
        node_name = tree.item(node_id, "text")

        for item in data:
            if item.get(text_key) == node_name:
                return item

            if item.get("type") == "folder" and "children" in item:
                result = TreeBuilder.get_node_data(tree, node_id, item["children"], text_key)
                if result:
                    return result

        return None


class SelectionManager:
    """选择状态管理器 - 支持多选框风格的选择"""

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self._checked_items: set = set()
        self._indeterminate_items: set = set()

    def toggle_check(self, item_id: str) -> None:
        """
        切换选中状态

        Args:
            item_id: 节点ID
        """
        if item_id in self._checked_items:
            self._checked_items.discard(item_id)
        else:
            self._checked_items.add(item_id)

        self._update_children_state(item_id)
        self._update_parent_state(item_id)
        self._refresh_display()

    def check(self, item_id: str) -> None:
        """
        选中节点

        Args:
            item_id: 节点ID
        """
        self._checked_items.add(item_id)
        self._update_children_state(item_id)
        self._update_parent_state(item_id)
        self._refresh_display()

    def uncheck(self, item_id: str) -> None:
        """
        取消选中节点

        Args:
            item_id: 节点ID
        """
        self._checked_items.discard(item_id)
        self._indeterminate_items.discard(item_id)
        self._update_children_state(item_id)
        self._update_parent_state(item_id)
        self._refresh_display()

    def is_checked(self, item_id: str) -> bool:
        """
        检查节点是否选中

        Args:
            item_id: 节点ID

        Returns:
            是否选中
        """
        return item_id in self._checked_items

    def get_checked_items(self) -> List[str]:
        """获取所有选中的节点ID"""
        return list(self._checked_items)

    def check_all_in_folder(self, folder_id: str) -> None:
        """选中文件夹内的所有内容"""
        for child in self.tree.get_children(folder_id):
            self._checked_items.add(child)
            self.check_all_in_folder(child)

    def _update_children_state(self, parent_id: str) -> None:
        """更新子节点状态"""
        for child in self.tree.get_children(parent_id):
            if child in self._checked_items:
                self._checked_items.add(child)
                self._update_children_state(child)

    def _update_parent_state(self, item_id: str) -> None:
        """更新父节点状态"""
        parent = self.tree.parent(item_id)
        if not parent:
            return

        children = self.tree.get_children(parent)
        all_checked = all(child in self._checked_items for child in children)
        any_checked = any(child in self._checked_items or child in self._indeterminate_items for child in children)

        if all_checked:
            self._indeterminate_items.discard(parent)
            self._checked_items.add(parent)
        elif any_checked:
            self._checked_items.discard(parent)
            self._indeterminate_items.add(parent)
        else:
            self._checked_items.discard(parent)
            self._indeterminate_items.discard(parent)

        self._update_parent_state(parent)

    def _refresh_display(self) -> None:
        """刷新显示状态"""
        pass


if __name__ == "__main__":
    print("=" * 50)
    print("TreeSelector 模块 - 使用示例")
    print("=" * 50)
    print("""
使用示例：

from tkinter import ttk
from tree_selector import TreeSelector, TreeBuilder

# 1. 创建树状图
tree = ttk.Treeview(root)

# 2. 构建数据
data = [
    {"title": "文件夹A", "type": "folder", "children": [
        {"title": "文件1.mp3", "type": "file"},
        {"title": "文件2.mp3", "type": "file"}
    ]},
    {"title": "文件3.mp3", "type": "file"}
]

# 3. 从API数据构建树
TreeBuilder.build_from_api_data(tree, data)

# 4. 创建选择管理器
selector = TreeSelector(tree)

# 5. 使用选择功能
selector.select_all()           # 全选
selector.invert_selection()    # 反选
selector.deselect_all()         # 取消全选

# 6. 获取选中项
selected = selector.get_selected_leaf_items()  # 只获取文件
selected = selector.get_selected_items()       # 获取所有选中项

# 7. 高级功能
selector.expand_all()           # 展开所有
selector.print_tree_structure() # 打印树结构（调试）

# 8. 选择管理（支持复选框逻辑）
manager = SelectionManager(tree)
manager.check("节点ID")         # 选中
manager.toggle_check("节点ID")  # 切换状态
""")
