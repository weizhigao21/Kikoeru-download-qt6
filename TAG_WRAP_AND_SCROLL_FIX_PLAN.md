# 作品列表：标签换行显示 & 滚动位置重置 — 分析与方案

> 日期：2026-08-07
> 涉及文件：`src/ui/qt/works_list.py`、`src/ui/qt/main_window.py`
> 参考实现：`src/ui/qt/detail_panel.py` 的 `FlowTags`（已实现标签流式换行）
>
> **实施状态：✅ 已于 2026-08-07 实施完成**（v2.0.6），无头验证全部通过，见文末「七、实施记录」。

---

## 一、现状

### 1.1 标签显示（问题 1）

作品列表卡片由 `WorkCardDelegate(QStyledItemDelegate)` 用 QPainter 全绘制，**没有 widget、没有 FlowLayout**。标签布局函数：

`works_list.py:155-168` `tag_layout()`

```python
def tag_layout(self, work, rect, extra):
    fm = QFontMetrics(SMALL)
    x = rect.left() + 8 + self.THUMB_W + 12
    y = rect.top() + 96 + extra
    h = 22
    out = []
    for tag in tag_names(work)[:12]:     # 最多 12 个
        w = fm.horizontalAdvance(tag) + 16
        if x + w > rect.right() - 8:     # 超出右边界直接 break
            break                        # ← 不换行，只显示一排
        out.append((tag, QRect(x, y, w, h)))
        x += w + 6
    return out
```

行为：标签多时**只显示第一排能放下的数量**，后面的全部丢弃。`tag_layout` 被三处共用：`paint`（绘制，296 行）、`_tag_at`（点击命中检测，389 行）。

卡片高度：`CARD_H = 155`，`sizeHint`（229-237 行）目前**只**在标题超过 1 行时 `+ TITLE_LINE_H(26)`，完全没考虑标签行数。

对照参考：`detail_panel.py:31-107` 的 `FlowTags` 已实现同样的标签流式换行（`_tag_rects` 中 `if x + w > self.width() and x > 0: x = 0; y += h + gap`），可直接借鉴算法。

### 1.2 滚动位置（问题 2）

- `WorksListModel.set_works()`（`works_list.py:66-69`）用 `beginResetModel()/endResetModel()` 全量重建。
- 全项目无任何 `scrollToTop()` / `verticalScrollBar().setValue()` 逻辑。
- QListView 在 model reset 后会**尽力维持原滚动位置（按 index）**，但翻页/搜索后数据完全变了，这个"维持"是错误行为 —— 用户看到的就是滚动条停在旧位置对应的新行上，没有回到顶部。

`set_works` 的全部调用点（main_window.py）：

| 行号 | 场景 | 期望行为 |
|---|---|---|
| 275 | `_show_works`（翻页/搜索/刷新/tab 切换） | **回顶部** |
| 487 | 详情「刷新作品信息」后重刷当前列表 | 保持位置 |
| 809 | 隐藏作品后从列表移除该行 | 保持视口位置 |
| 851 | 删除下载记录后重新过滤 | 保持位置 |

---

## 二、实现困难分析

### 2.1 标签换行的困难

1. **Delegate 全绘制架构下没有现成流式布局可用**
   QListView 卡片是画出来的，无法直接塞 `FlowLayout`/`QHBoxLayout`。必须自算"流式布局"：维护 `(x, y)` 游标，超右边界换行。算法本身不难（照抄 `FlowTags._tag_rects`），但所有与布局相关的逻辑都要**共用同一个布局函数**，否则绘制、尺寸测量、点击命中三处会对不上。

2. **卡片高度必须随标签行数动态变化（sizeHint 同步）**
   标签换行后，第 2 行标签会画到 `y = 96+22+gap`，若 `sizeHint` 仍返回 `CARD_H=155`，会被下一张卡片覆盖。所以 `sizeHint` 必须按标签行数加高：
   `h = CARD_H + 标题额外行 + (标签行数-1) * (TAG_H + GAP)`。
   **困难点**：`sizeHint` 里拿宽度只有 `option.rect.width()`，首次布局时可能无效（代码里已 fallback 600）。宽度不准 → 标签行数算错 → 高度忽高忽低、滚动时卡片跳变。标题换行目前"最多 2 行"的保守设计就是这个原因，标签换行也要做同样的**行数上限**兜底。

3. **性能：`sizeHint` 被高频调用**
   滚动、resize、hover 都会触发 `sizeHint`，每个可见 item 都要跑一遍标签换行（每个标签一次 `horizontalAdvance`）。标签多 + 列表长时会产生可感知的开销。需要做布局缓存（详见方案 3.1 第 4 条）。

4. **与「版本标签」行的垂直空间关系**
   `edition_layout` 画在 `y=48+extra` 行，标签从 `y=96+extra` 开始。标签换行向下扩展，不与其冲突；但要给卡片底部留 padding，并限制最大行数（建议 2~3 行），防止标签特别多（几十个）的作品把卡片撑得过高、挤爆一屏。

5. **命中检测与绘制必须同步**
   `_tag_at`（382-392 行）依赖 `tag_layout` 返回值做 `QRect.contains` 判断。改换行后因为共用函数**会自动同步**，但前提是 `paint`/`_tag_at`/`sizeHint` 三处的 `extra`（标题偏移）计算保持一致 —— 这三处现在分别独立计算 `extra`，改的时候要统一口径，最好抽一个公共方法。

6. **`[:12]` 上限的处理**
   现在最多取 12 个标签。换行后是否放开数量？建议：保留"最多 12 个标签"，但 12 个可以占多行（第 1 行放不下就换行继续），这样既不无限膨胀，又让多的标签能被看到。若希望显示更多，可考虑上限放宽到 20~24 + 行数上限 2 行。

### 2.2 滚动重置的困难

1. **必须区分「数据源切换」与「局部刷新」两类场景**
   翻页/搜索/刷新要回顶部；详情刷新、隐藏删除后要保持位置。**不能简单在 `set_works` 里无条件 scrollToTop**，否则删除一个作品视口就跳回顶部，体验更差。

2. **重置时机**
   `scrollToTop()` 必须在 `endResetModel()` **之后**调用。模型 reset 是同步的，所以在 `set_works` 返回后立即调一般有效；但 ScrollPerPixel 模式 + sizeHint 动态行高下，QListView 的布局/滚动状态可能要到事件循环下一轮才稳定，稳妥做法是 `QTimer.singleShot(0, ...)` 兜底（避免个别场景下"回到顶部但内容还没铺好"的闪烁）。

3. **所有入口都要覆盖**
   除了 `_show_works`，还有 487/809/851 三处直接调 `set_works`，以及 `_on_search_loaded`、`_load_downloads` 等。方案要收敛到一个统一的入口，避免漏改。

---

## 三、方案设计

### 3.1 方案 A：标签自动换行（改 `works_list.py`）

**改动点：**

**① 新增常量**（类属性，与标题 `TITLE_LINE_H` 并列）：

```python
TAG_H = 22      # 单个标签高（现 tag_layout 内写死 22，抽出）
TAG_GAP = 4     # 标签行间距（对齐 FlowTags）
TAG_MAX_LINES = 2   # 标签最多行数（兜底，防超高卡片）
```

**② 重写 `tag_layout` 为流式换行**（算法照抄 `FlowTags._tag_rects`）：

```python
def tag_layout(self, work, rect, extra):
    """标签流式布局：放不下自动换行，最多 TAG_MAX_LINES 行。"""
    fm = QFontMetrics(SMALL)
    out = []
    x = rect.left() + 8 + self.THUMB_W + 12
    y = rect.top() + 96 + extra
    right = rect.right() - 8
    for tag in tag_names(work)[:12]:
        w = fm.horizontalAdvance(tag) + 16
        if x + w > right:
            line = (y - (rect.top() + 96 + extra)) // (self.TAG_H + self.TAG_GAP)
            if line >= self.TAG_MAX_LINES:      # 达到行数上限，停止
                break
            x = rect.left() + 8 + self.THUMB_W + 12
            y += self.TAG_H + self.TAG_GAP
        out.append((tag, QRect(x, y, w, self.TAG_H)))
        x += w + 6
    return out
```

（`paint` 与 `_tag_at` 因共用本函数**自动同步**，无需改动。）

**③ `sizeHint` 按标签行数加高**（关键：与 paint 用同一套口径）：

```python
def _tag_row_count(self, work, width):
    """复用 tag_layout 逻辑，统计标签占几行（宽度不足时按保守值 600 兜底）。"""
    # 用 tag_layout 的返回值的最大 y 反推行数，或直接轻量重算行数

def sizeHint(self, option, index):
    work = index.data(Qt.ItemDataRole.UserRole)
    h = self.CARD_H
    if isinstance(work, dict):
        width = option.rect.width() if (option.rect.isValid() and option.rect.width() > 0) else 600
        title_w = width - 8 - self.THUMB_W - 12 - 8
        if self._title_line_count(...) > 1:
            h += self.TITLE_LINE_H
        rows = self._tag_row_count(work, width - 8 - self.THUMB_W - 12 - 8)
        if rows > 1:
            h += (rows - 1) * (self.TAG_H + self.TAG_GAP)   # 最多 (TAG_MAX_LINES-1) 行增量
    return QSize(0, h)
```

**④ 布局缓存（性能）**：在 Delegate 上维护 `self._tag_cache = {}`，key 为 `(work["id"], 可用宽度取整)`，value 为 `(行数, [(tag, QRect)])`。`tag_layout` 命中缓存直接返回；`set_thumb`/reset 时清理。同时注意 `extra` 会影响 y 偏移 —— 缓存只缓存"每行第几个、宽度"这类**与 y 无关**的布局结果，y 偏移在取用时叠加，或用 `(work_id, width, extra)` 作 key。简单起见建议**缓存换行结果（每行标签列表），y 由调用方根据 extra 计算**。

**⑤ 卡内布局核对**：`CARD_H=155`，`y=96` 起画标签，2 行标签 = `96 + 22 + 4 + 22 = 144`，距底部 `155` 还有 11px padding，够用且不碰版本标签行（48 行），无需改其它元素。

### 3.2 方案 B：滚动位置重置（改 `works_list.py` + `main_window.py`）

**① 在 `WorksListView` 上收敛一个统一入口**（推荐，避免每个调用点各自处理）：

```python
def set_works(self, works, scroll_to_top=False):
    """替换数据；scroll_to_top=True 时重置滚动条到顶部（翻页/搜索/刷新用）。"""
    self.model().set_works(works)
    if scroll_to_top:
        # reset 后 view 布局可能下一帧才稳定，延迟一帧保证滚动生效
        QTimer.singleShot(0, self.scrollToTop)
```

> 若实测同步 `scrollToTop()` 稳定生效，可去掉 `singleShot(0)` 直接调用，两者择一（建议先同步试，不行再兜底）。

**② 调用点按场景传参**（main_window.py 共 4 处）：

| 行号 | 现有代码 | 改为 |
|---|---|---|
| 275 | `self.model.set_works(works)` | `self.list_view.set_works(works, scroll_to_top=True)` |
| 487 | `self.model.set_works(self.works)` | `self.list_view.set_works(self.works)` （保持位置） |
| 809 | `self.model.set_works(self.works)` | `self.list_view.set_works(self.works)` （保持视口） |
| 851 | `self.model.set_works(self.works)` | `self.list_view.set_works(self.works)` （保持位置） |

> 注意 `_show_works` 内 `self.model` 与 `self.list_view` 的关系：确认 MainWindow 里 model 与 list_view 的引用（`self.model` 即 `self.list_view.model()`），改用 view 入口后统一从 view 访问。

**③ 顺带确认**：`_on_search_loaded`、`_load_downloads` 最终都走 `_show_works`，方案 B 覆盖后无需额外处理。

---

## 四、改动清单

| 文件 | 位置 | 改动 |
|---|---|---|
| `works_list.py` | 类常量（~94 行） | 新增 `TAG_H/TAG_GAP/TAG_MAX_LINES` |
| `works_list.py` | `tag_layout`（155-168 行） | 单行 → 流式换行 + 行数上限 |
| `works_list.py` | `sizeHint`（229-237 行） | 按标签行数加高卡片 |
| `works_list.py` | 新增 `_tag_row_count` / 布局缓存 | 供 sizeHint 使用 + 性能优化 |
| `works_list.py` | `WorksListView`（304 行） | 新增 `set_works(works, scroll_to_top)` 入口 |
| `main_window.py` | 275 / 487 / 809 / 851 行 | 改用 `list_view.set_works(...)` 并按场景传参 |

**不需要改**：`paint`、`_tag_at`（共用 `tag_layout` 自动同步）、`detail_panel.py`（FlowTags 已正常）。

---

## 五、风险与注意事项

1. **宽度抖动**：sizeHint 的宽度 fallback 逻辑与 paint 的实际 `rect` 宽度可能不一致（首次布局 600 vs 实际列宽），会导致刚渲染时高度跳一次。可接受（标题换行已有同类行为），后续若明显可再优化为按列宽缓存。
2. **缓存失效**：标签布局缓存需在 `set_works`（数据替换）和窗口 resize（列宽变化）时清理，否则高度/绘制错乱。resize 可由 `WorksListView.resizeEvent` 触发 `delegate().clear_cache()`。
3. **行数上限的取舍**：`TAG_MAX_LINES=2` 时，12 个标签在窄窗口下第 2 行也放不下会丢弃 —— 与现状"只显示一排"相比已是明显改善；若用户希望看到全部标签，可放开上限到 3 行或去掉 `[:12]` 改为 `[:20]`（卡片更高，需权衡列表密度）。
4. **滚动重置与卡片高度变化的耦合**：标签换行让"翻页后高度不同"，scrollToTop 不受影响；但"保持位置"场景（487/809/851）下若某作品标签从 1 行变 2 行，视口会轻微偏移，属可接受范围。
5. **回归验证点**：翻页后滚动条回顶；搜索/刷新回顶；隐藏作品不跳顶；删除记录不跳顶；标签点击搜索仍精确命中；标签多/少、窗口窄/宽两种极端下卡片高度与绘制一致无重叠。

---

## 六、验收标准

- [x] 标签超过一行宽度时自动换行显示，不再只显示一排
- [x] 标签最多 2 行（或按定稿上限），卡片高度随标签行数自适应，无重叠/截断
- [x] 翻页、搜索、刷新后滚动条回到顶部
- [x] 详情刷新、隐藏作品、删除记录后滚动位置保持不变
- [x] 标签点击命中与绘制位置完全一致（换行后仍可点击搜索）
- [x] 长列表滚动无卡顿（布局缓存生效）

---

## 七、实施记录（2026-08-07）

**改动文件：**

| 文件 | 改动 |
|---|---|
| `works_list.py` | 新增常量 `TAG_H/TAG_GAP/TAG_MAX_LINES`；`tag_layout` 改流式换行（最多 2 行）；新增 `_tag_lines`（行分组 + 缓存）、`_tag_width`（宽度缓存）、`clear_cache`；`sizeHint` 按标签行数加高；`WorksListView` 新增 `set_works(works, scroll_to_top)` 与 `resizeEvent` 缓存清理 |
| `main_window.py` | 275 行翻页/搜索/刷新 → `set_works(..., scroll_to_top=True)`；487/809/851 行局部刷新 → 默认保持位置 |
| `CHANGELOG.md` | 新增 v2.0.6 条目 |

**无头验证结果（QT_QPA_PLATFORM=offscreen，系统 Python 3.10 + PyQt6）：**

- 标签区 212px：12 个标签换行成 2 行（显示 8 个，余下丢弃）
- 标签区 800px：1 行显示全部 12 个
- `sizeHint`：标签 2 行时高度 155→181（+26），与绘制一致
- 极窄宽度：行数始终 ≤2，不撑爆卡片
- 标题 2 行（extra=26）：标签整体下移 26，偏移一致
- 布局缓存命中/清理正常
- 滚动：翻页 `scroll_to_top=True` 后滚动条归 0；局部刷新 `False` 后位置保持（150→150）
