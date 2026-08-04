# Qt6 迁移计划（Kikoeru-download-qt6）

> 状态：阶段 0-5 全部完成（Qt6 迁移交付 v2.0.0） · 目标版本：v2.0.0（Qt6） · 适用代码基线：v1.61.0
> 本文档只规划 **UI 层** 重写；业务层（下载管理、数据库、API、翻译/转换服务）零改动复用。

---

## 1. 背景与目标

### 1.1 现状问题（tkinter）
- 列表页每页 20 张卡片 × ~17 个 widget = **340 个 widget**，翻页/滚动时全量构建销毁，是卡顿主因
- `root.after(0, fn)` 手动调度跨线程 UI 更新，依赖 `_nav_generation` 防过期，易漏导致跨线程操作 widget
- `ImageTk.PhotoImage` 必须在主线程创建，缩略图加载主线程压力大
- 样式依赖 `ttk.Style` 手写颜色，观感老旧，HiDPI 支持弱

### 1.2 迁移目标
| 目标 | 达成手段 |
|---|---|
| 长列表流畅 | `QListView` + `QAbstractListModel` + `QStyledItemDelegate` 内置虚拟化 |
| 跨线程安全 | signal/slot 队列连接，自动回主线程 |
| 现代观感 | QSS 样式表（圆角、hover、高 DPI） |
| 图片性能 | 后台线程 `QImage` 解码，主线程 `QPixmap.fromImage` |

### 1.3 原则
1. **UI 与业务严格分离**：`src/database/`、`src/download/`、`src/services/`、`src/api_client.py`、`src/config.py`、`src/utils.py` **不修改**
2. **不可渐进共存**：tkinter 与 Qt6 不能混用在同一窗口树，切换是一次性整体替换
3. 迁移期间保留 tkinter 版本可运行，Qt6 版在独立包结构下并行开发，验收通过后切换入口

---

## 2. 现状盘点

### 2.1 UI 层文件与职责

| 文件 | 行数 | 职责 |
|---|---|---|
| `gui_app.py` | 224 | `WorkApp` 组合 7 个 mixin；线程池/数据库初始化；`_on_close` 清理 |
| `gui_app_ui.py` | 330 | `UISetupMixin`：样式、顶栏/列表区/详情区/底栏 4 区搭建、底部任务槽 |
| `gui_app_nav.py` | 379 | `NavigationMixin`：tab 切换、数据加载导航、翻页、按钮状态 |
| `gui_app_events.py` | 126 | `EventMixin`：搜索历史、滚轮、快捷键 |
| `src/ui/list_card.py` | 500 | `ListCardMixin`：卡片创建/更新、tags Canvas 绘制、翻译交互、编辑弹窗 |
| `src/ui/list_mixin.py` | 220 | `ListMixin`：`display_works_list`、缩略图批量加载 |
| `src/ui/search_mixin.py` | 419 | `SearchMixin`：标签/关键词/厂商搜索、历史恢复 |
| `src/ui/filter_mixin.py` | 298 | `FilterMixin`：隐藏已下载过滤、`PAGE_SIZE=20` |
| `src/ui/detail_mixin.py` | 354 | `DetailMixin`：详情面板、懒加载声优/厂商、大图 |
| `src/ui/detail_actions.py` | 158 | `DetailActionsMixin`：隐藏作品/删记录/刷新信息 |
| `src/ui/gui_download.py` | 330 | `DownloadWindow`（Toplevel）：tracks 树、选择、下载提交 |
| `src/ui/gui_download_manager.py` | 377 | `DownloadManagerWindow`（Toplevel）：任务列表/进度 |
| `src/ui/gui_settings.py` | 492 | `SettingsWindow`（Toplevel）：配置/缓存/翻译设置 |
| `src/ui/tree_selector.py` | 230 | `TreeSelector`：Treeview 选择操作工具 |
| `src/ui/fonts.py` | 45 | 字体集中管理（tkfont 元组） |

### 2.2 线程模型（现状）
- `_thumb_pool`（8 线程）、`_data_pool`（4 线程）→ 缩略图/数据加载
- 裸 `threading.Thread` + `root.after(0, ...)` 调度 UI 更新
- `_nav_generation` 递增机制丢弃过期请求结果

---

## 3. 目标架构（Qt6）

### 3.1 组件树
```
QApplication
└── MainWindow (QMainWindow)
    ├── TopBarWidget        ← tab 切换、搜索框、排序、状态栏（原 UISetupMixin 顶栏）
    ├── WorksListView       ← QListView + WorksListModel + WorkCardDelegate（原 list_card/list_mixin）
    ├── DetailPanel         ← QScrollArea 内嵌 QWidget（原 detail_mixin/detail_actions）
    └── BottomBarWidget     ← 下载任务条、翻页、设置入口（原 UISetupMixin 底栏）
子窗口（QDialog，模式窗口）：
    ├── DownloadDialog          ← 原 gui_download.py（QTreeView + 自定义 Model）
    ├── DownloadManagerDialog   ← 原 gui_download_manager.py（QTableView）
    └── SettingsDialog          ← 原 gui_settings.py（QTabWidget）
```

### 3.2 类拆分建议（从 7 个 mixin 收敛为 5 个 UI 类）
| 原 mixin | Qt6 归属 |
|---|---|
| `ListMixin` + `ListCardMixin` | `WorksListView`（视图）+ `WorksListModel`（数据）+ `WorkCardDelegate`（绘制） |
| `DetailMixin` + `DetailActionsMixin` | `DetailPanel` |
| `SearchMixin` + `FilterMixin` | `WorksListModel`（数据过滤）+ `TopBarWidget`（交互） |
| `NavigationMixin` + `EventMixin` | `MainWindow`（导航编排） |
| `UISetupMixin` | `TopBarWidget` / `BottomBarWidget` + QSS |

### 3.3 文件布局
```
src/ui/qt/
    ├── __init__.py
    ├── app.py                  # QApplication 入口（替代 gui_app.py 的 __main__）
    ├── main_window.py          # MainWindow：导航/翻页/状态编排
    ├── top_bar.py / bottom_bar.py
    ├── works_list.py           # WorksListView + WorksListModel + WorkCardDelegate
    ├── detail_panel.py
    ├── download_dialog.py      # 原 gui_download.py
    ├── download_manager_dialog.py
    ├── settings_dialog.py
    ├── workers.py              # DataWorker / ThumbnailWorker / GenerationGuard
    ├── styles.qss              # QSS 样式表
    └── qt_fonts.py             # fonts.py 的 Qt 适配层（QFont 构造）
保留（业务层，不动）：
    src/database/  src/download/  src/services/  src/api_client.py  src/config.py  src/utils.py
```

---

## 4. 核心组件设计

### 4.1 列表虚拟化（核心价值点）
```python
# works_list.py
class WorksListModel(QAbstractListModel):
    worksChanged = pyqtSignal()
    def data(self, index, role):
        if role == Qt.UserRole:
            return self._works[index.row()]      # 完整 dict，delegate 自取
        if role == Qt.SizeHintRole:
            return QSize(0, 96)
        return None

class WorkCardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        work = index.data(Qt.UserRole)
        r = option.rect
        # hover 高亮：State_MouseOver
        bg = "#E3F2FD" if (option.state & QStyle.State_MouseOver) else "#FFFFFF"
        painter.fillRect(r, QColor(bg))
        painter.drawPixmap(r.left()+8, r.top()+8, self._thumbs.get(work["id"]))
        # 标题/ID/标签矩形：painter.drawText / drawRoundedRect
    def sizeHint(self, option, index):
        return QSize(0, 96)

class WorksListView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(WorkCardDelegate(self))
        self.setModel(WorksListModel(self))
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
```
- **虚拟化收益**：widget 数量恒定（仅可见行），滚动由 Qt 原生滚动条驱动
- **点击/双击**：`clicked`/`doubleClicked` 信号 → 详情/下载窗口
- **tags 绘制**：delegate 内 `drawRoundedRect` + `drawText`，替代 `_draw_tags_on_canvas`

### 4.2 线程 Worker 模式（替代 threading + after）
```python
# workers.py
class DataWorker(QObject):
    loaded = pyqtSignal(int, list, int)      # (generation, works, max_page)
    failed = pyqtSignal(int, str)
    def __init__(self):
        super().__init__()
        self.gen = 0
    def fetch_works(self, page, tab):
        g = self.gen
        try:
            api = get_api_client()
            works, max_page = api.fetch_works_page(page)
            self.loaded.emit(g, works, max_page)
        except Exception as e:
            self.failed.emit(g, str(e))

# MainWindow 侧
self.worker.loaded.connect(self._on_data_loaded)
def _on_data_loaded(self, gen, works, max_page):
    if gen != self._nav_generation:   # 过期丢弃（沿用现有机制）
        return
    self.model.set_works(works)       # model 更新自动触发视图刷新
```
- **线程管理**：`QThread` + `moveToThread`，线程随窗口销毁自动回收（`destroyed` → `quit`+`wait`），替代 `_on_close` 手动 shutdown
- **缩略图**：`ThumbnailWorker` 后台 `QImage` 解码（QImage 线程安全）+ LRU 缓存 QPixmap（`memory_cache` 复用）

### 4.3 图片管线
```
后台线程:  URL → requests 下载 → PIL 解码/缩略(180x180) → QImage（线程安全）
主线程:    信号携带 QImage → QPixmap.fromImage() → delegate 缓存/绘制
```
- 磁盘缓存（`image_cache/`）逻辑复用 `src/database/cache.py`，仅把 `ImageTk.PhotoImage` 替换为 `QPixmap`

### 4.4 树与表格
| 原控件 | Qt6 |
|---|---|
| `ttk.Treeview`（下载窗口 tracks 树） | `QTreeView` + 自定义 `QAbstractItemModel`（`TreeSelector` 逻辑改写为 model 方法：全选/反选/按目录选） |
| 下载管理任务列表 | `QTableView` + 自定义 model（`_STATUS_MAP` 逻辑保留为 delegate 颜色） |
| 设置页 | `QTabWidget`（替代 ttk.Notebook）+ `QSettings` 或沿用 `config.py` |

### 4.5 字体适配（复用 fonts.py 常量）
```python
# qt_fonts.py —— 常量从 src/ui/fonts.py 导入，仅构造方式变化
from src.ui.fonts import UI_FONT_FAMILY, MONO_FONT_FAMILY, EMOJI_FONT_FAMILY

def qfont(family, size, bold=False):
    f = QFont(family)
    f.setPointSize(size)
    f.setBold(bold)
    return f

DEFAULT   = qfont(UI_FONT_FAMILY, 10)
TITLE     = qfont(UI_FONT_FAMILY, 14, True)
EMOJI     = qfont(EMOJI_FONT_FAMILY, 10)
# get_tag_font() → QFontMetrics(标签测量)
```

---

## 5. QSS 样式设计

色板沿用 [gui_app_ui.py](file:///g:/code/音声下载/gui_app_ui.py) 的 `COLORS`（primary #1976D2 / bg #f5f5f5 / card #ffffff / accent #FF9800 …），通过 Python 常量生成 QSS 字符串（QSS 本身无变量）：

```python
# styles.py —— 由 COLORS 生成 QSS，避免两处维护
QSS = f"""
QMainWindow {{ background: {C["bg"]}; }}
QPushButton {{ background: {C["primary"]}; color: white; border-radius: 4px; padding: 6px 12px; }}
QPushButton:hover {{ background: #1565C0; }}
QPushButton:disabled {{ background: {C["border"]}; color: {C["text_hint"]}; }}
QListView {{ background: {C["card_bg"]}; border: 1px solid {C["border"]}; }}
QScrollBar:vertical {{ width: 10px; background: {C["bg"]}; }}
QScrollBar::handle:vertical {{ background: {C["border"]}; border-radius: 5px; }}
QTreeView::item:selected {{ background: #0078D7; color: white; }}
"""
```

---

## 6. 分阶段实施计划

> 每个阶段结束产物**可运行、可验收**；阶段 0-4 期间 tkinter 版保持为默认入口。

### 阶段 0：环境与骨架
- 安装 PyQt6（`pip install PyQt6`）；新增 `src/ui/qt/` 包与 `app.py`
- `MainWindow` 空壳 + 顶栏/底栏静态控件 + QSS 挂载
- 验收：`python -m src.ui.qt.app` 弹出窗口，样式正确，业务层零修改

### 阶段 1：列表页核心
- `WorksListModel` + `WorkCardDelegate`（封面/标题/ID/标签绘制、hover）
- 翻页/数据加载接入 `DataWorker`；缩略图接入 `ThumbnailWorker`
- 验收：推荐/最新/下载 tab 翻页流畅（对照 tkinter 版），缩略图异步加载无卡顿，点击打开详情（详情先用占位）
- ✅ 已完成：真实 DB 20 条 + 真实网络缩略图 20 张加载验证通过（`rows=20 thumbs=20`），单击/双击/翻页/退出均无崩溃（详见下方"阶段进度记录"）

### 阶段 2：详情面板 + 搜索/过滤
- `DetailPanel` 完整字段、懒加载声优/厂商、大图、翻译/隐藏/删除操作
- 搜索（标签/关键词/厂商）、过滤（隐藏已下载）、排序、搜索历史回退
- 验收：与 tkinter 版功能对拍通过（同数据同操作同结果）；长列表滚动 fps 明显优于 tkinter
- ✅ 已完成：冒烟验证 35/35 通过（offscreen + FakeAPI + FakeDLHistory 25 条 + 确定性图片），覆盖详情展示/大图、关键词/厂商搜索、搜索历史回退、下载 tab 排序与本地分页、隐藏已下载过滤、刷新/删除记录、懒加载合并、退出线程回收（详见"阶段进度记录"）

### 阶段 3：三个对话框
- `DownloadDialog`（tracks 树、全选/反选、URL 刷新、下载提交）
- `DownloadManagerDialog`（任务列表、进度、状态映射）
- `SettingsDialog`（全部设置项、缓存管理）
- 验收：三个窗口功能与 tkinter 版一致；下载流程端到端可跑通

### 阶段 4：联调打磨
- 快捷键、滚轮、窗口 resize；`_on_close` 线程池/数据库清理迁移到 Qt 生命周期
- QSS 细化（hover/选中/禁用态）；HiDPI 检查
- 验收：全功能回归清单过一遍；`tasksel` 内存占用/滚动帧率对比达标

### 阶段 5：切换入口与发布
- 入口切到 `app.py`，移除/归档 tkinter 版（保留分支可回退）
- CHANGELOG 记录 v2.0.0；PyInstaller 打包验证（体积预期 +40~60MB）
- 验收：打包版全功能可用

---

## 7. 风险与注意事项

| 风险 | 说明 | 对策 |
|---|---|---|
| **不可渐进** | tkinter 与 Qt6 不能共存一窗口树 | 独立包并行开发，验收后一次性切换 |
| **QPixmap 主线程限制** | 与 PhotoImage 同理，后台只能造 QImage | 后台 QImage 解码，主线程 fromImage（已列入 4.3） |
| **Treeview → QTreeView** | 选择/路径映射逻辑重写成本最高 | `TreeSelector` 的算法转为 model 方法，先做单元对照 |
| **字体度量差异** | `tkfont.measure` vs `QFontMetrics` | 标签/文本截断统一走 `QFontMetrics`，替换点已列在 4.5 |
| **打包体积** | PyQt6 增大约 40-60MB | 用 `PyQt6` 官方 wheel 即可，无需裁剪（本工具内网分发） |
| **grab_set 模态** | 下载窗口依赖模态阻塞 | `QDialog.exec()` / `setModal(True)` 等价 |
| **调试回归成本** | 4800 行重写 | 阶段 0-4 每阶段功能对拍 + 验收清单（见第 6 节） |

---

## 8. 性能预期（验收参照）

| 指标 | tkinter（v1.61.0） | Qt6 目标 |
|---|---|---|
| 列表 widget 数量 | ~340/页 | 恒定 ~10-12（仅可见行） |
| 翻页耗时（数据已缓存） | ~150-300ms | ~50ms 内（纯模型刷新） |
| 长列表滚动（5000 条） | 明显掉帧 | 流畅 |
| 缩略图异步加载 | 8 线程 + 主线程 PhotoImage | 后台 QImage + 主线程轻量转换 |

---

## 9. 回退策略
- Qt6 版通过独立包 `src/ui/qt/` 交付，默认入口可切换
- 阶段 5 之前 `gui_app.py`（tkinter）始终可用；切换后若发现严重问题，git 回退到迁移前 tag 即可

---

## 10. 阶段进度记录

### 阶段 0-1 完成（2026-08-04）
- 已验证链路：真实 DB（20 条/页 9）→ `DataWorker` → `WorksListModel`；真实网络缩略图 20 张 → `ThumbnailWorker` → `QByteArray` → 主线程 `QImage` → delegate 缓存/绘制；单击/双击/翻页/关闭均无崩溃
- 跨线程图片传递最终方案：`QByteArray` 携带 RGB 原始数据（Qt 内置 metatype，queued 可排队），主线程 `QImage(bytes, w, h, w*3, Format_RGB888)` 重建

### 阶段 0-1 关键坑（后续阶段避免重踩）
1. **PyQt6 `QImage` 无 `detach()`**：`qimg.detach()` 抛 AttributeError，且该异常在 Qt C++ 槽调用链中会触发 `qFatal`（0xC0000409）直接 abort，无 Python traceback。改用 `qimg.copy()`（实测为深拷贝，摆脱外部字节缓冲生命周期约束）
2. **QListView 无 `delegate()` 方法**：应使用 `itemDelegate()`；`src/ui/qt/works_list.py` 中 `WorksListView.delegate()` 为便捷访问
3. **Python 槽内抛异常必须 try/except 兜底**：任何从 C++ 逃逸的 Python 异常（如 `None.quit()` 的 AttributeError）都会 qFatal 崩溃
4. **`Qt.AlignmentFlag` 类型**：Qt6 的 `addWidget(widget, 0, 0)` 第二个参数需 `Qt.AlignmentFlag`，传 int 会 TypeError
5. **queued 连接传参**：Python 原生 `bytes` 无法排队（静默丢弃，count=0），必须用 `QByteArray`；`list`/`str`/`int` 可直接传

### 阶段 2 完成（2026-08-04）
- `DetailPanel`（QScrollArea）：标题译/原切换 + 复制、封面大图（360x200 等比）、`FlowTags` 圆角标签流式布局、ID 复制、可点击厂商 `CircleLabel`、声优、其他语言版本、隐藏/刷新/删除下载记录三按钮（删除按钮仅已下载时可见）
- `DataWorker` 扩展 `search`（id/keyword/circle/tag）/`downloads`/`work_detail` 三个异步通道；`ThumbnailWorker` 扩展 `detail_request/detail_ready` 大图通道
- `MainWindow` 编排：推荐/最新/下载三 tab、搜索（数字→ID 搜索，否则关键词）、厂商搜索、搜索历史回退（弹栈恢复搜索状态）、隐藏已下载过滤（`normalize_rj_id` + 下载 ID 缓存）、下载 tab 六种排序 + 本地分页（PAGE_SIZE=20）、详情懒加载（只刷详情面板避免滚动跳顶）与全量刷新（`_detail_refreshing` 标志区分、写回 works 缓存 + 下载历史详情）
- 冒烟验证：35/35 通过（offscreen + FakeAPI + FakeDLHistory 25 条 + 确定性图片打桩），退出线程回收、无崩溃

### 阶段 2 关键坑
1. **`_on_work_detail_loaded` 的刷新标志复位时机**：`detail_panel.set_refreshing(False)` 会复位面板内部 `_refreshing`，若先复位再读 `is_refreshing()` 判断刷新/懒加载分支会全部走错。必须先 `was_refreshing = getattr(self, "_detail_refreshing", False)` 再复位标志
2. **懒加载合并不能重建 model**：`_merge_lazy_detail` 中调 `model.set_works(...)` 会触发 beginResetModel，滚动位置跳顶。改为仅 `detail_panel.show_work(...)` 刷新详情
3. **状态文案里 `len(self.works)` 在 `_show_works` 执行前求值**：f-string 参数先于函数体求值，此时 `self.works` 还是旧列表，显示条数错误。改用参数 `len(works)`

### 阶段 3 完成（2026-08-04）
- `DownloadDialog`（`src/ui/qt/download_dialog.py`）：`TracksModel` 树模型（internalPointer 节点 dict + 预建父映射 + node_path 子目录路径）、三层 tracks 加载（DB 缓存 → API → 落库）、选区联动/全选递归、提交下载（`DownloadManager().submit` → 2 秒后自动关闭）
- `DownloadManagerDialog`（`src/ui/qt/download_manager_dialog.py`）：QTabWidget 双页（正在下载/已完成）、`_ActiveTaskModel` 6 列 + `_ProgressDelegate` 自绘进度条、observer→pyqtSignal 跨线程刷新、操作列 indexWidget 重试/取消按钮、已完成按 completed_at 降序取前 100
- `SettingsDialog`（`src/ui/qt/settings_dialog.py`）：左侧导航 + QStackedWidget 五页（下载/队列/存储/字幕/AI）、保存写 config.json + 同步 `src.config` 模块常量 + DownloadManager 队列模式 + 翻译服务 + db_dir 迁移；图片缓存大小统计/清除
- `MainWindow` 接入：双击 → DownloadDialog、下载管理/设置按钮（单实例防重入）、DownloadManager 依赖配置 + 启动 `restore_pending_tasks`、observer → 主线程信号（仅完成/失败集合变化时重查已下载 ID）、closeEvent 移除 observer + 四 DB 关闭
- 冒烟验证：8/8 通过（`_qt_stage3.py`，offscreen + FakeAPI + FakeDLHistory + FakeDlMgr）

### 阶段 3 关键坑
1. **pyqtSignal 不能作实例属性**：`self._downloads_changed = pyqtSignal()` 无 connect 方法；必须声明为类属性
2. **QShortcut 在 `PyQt6.QtGui`**：不在 QtWidgets
3. 进度列无 DisplayRole 数据（由 delegate 自绘），断言任务数据走 `Qt.ItemDataRole.UserRole`

### 阶段 4 完成（2026-08-04）
- 快捷键：`Ctrl+F`（QKeySequence.StandardKey.Find）聚焦搜索框并全选、`F5` 刷新、页码框 Enter 跳页；列表 Enter/双击统一走 `activated` 信号打开下载窗口（避免 doubleClicked+activated 双触发重复打开）
- 滚轮：QListView ScrollPerPixel 原生平滑滚动、QScrollArea 原生滚轮（tkinter 版 Canvas 劫持不再需要）
- resize：窗口最小尺寸 900x600（详情面板固定 400px 防列表被挤没）、FlowTags 宽度变化自动重排
- 冒烟验证：7/7 通过（`_qt_stage4.py`，QWheelEvent 发送到 viewport 断言滚动、QTest.keyClick 触发快捷键、resize 断言最小尺寸）
- `_on_close` 清理在阶段 3 已迁移到 Qt closeEvent（线程 quit+wait + DB close_all）

### 阶段 5 完成（2026-08-04）
- 入口切换到 Qt6：根目录新增 `app.py`（`python app.py`，或 `python -m src.ui.qt.app`），`src/ui/qt/app.py` 补 logging 配置
- tkinter 版归档：`gui_app.py` / `gui_app_ui.py` / `gui_app_nav.py` / `gui_app_events.py` 及 `src/ui/` 下 10 个 tkinter UI 模块（list_card/list_mixin/search_mixin/filter_mixin/detail_mixin/detail_actions/gui_download/gui_download_manager/gui_settings/tree_selector）移至 `legacy_tk/`；`src/ui/fonts.py` 因 Qt 版复用保留
- `src/__init__.py` 移除 tkinter UI 导出（DownloadWindow/SettingsWindow/DownloadManagerWindow），`src/ui/__init__.py` 清空导出
- 版本号 `src/config.py` VERSION → v2.0.0；CHANGELOG 新增 v2.0.0；README 更新（Qt6 描述/入口/项目结构/依赖/快捷键/虚拟滚动已实现）
- 验证：导入检查 + 全量回归脚本（_qt_context_menu/_qt_stage3/_qt_stage4/_qt_edition/_qt_circle_paging/_api_pagination）
