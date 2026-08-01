﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿# 音声作品浏览下载

一个基于 Tkinter 的桌面应用程序，用于浏览和下载 ASMR 音声作品。

**GitHub 仓库**：https://github.com/weizhigao21/Kikoeru-download

## 版本

**v1.54.0**（当前版本）

## 功能特性

### 浏览与搜索
- **三列表浏览**：支持"推荐作品"、"最新收录"和"下载作品"三个数据源切换
- **分页浏览**：支持按页查看作品列表，每页显示 20 个作品
- **隐藏下载作品**：在"推荐作品"和"最新收录"模式下，点击按钮切换"显示全部/隐藏下载"状态，快速过滤已下载作品
- **标签搜索**：点击任意标签快速筛选同类作品，支持多标签组合搜索（AND 交集），每个标签可单独移除
- **关键词搜索**：统一搜索框，自动识别输入为 RJ ID 或关键词进行模糊搜索
- **厂商搜索**：点击详情页厂商名称搜索该厂商的所有作品
- **ID 搜索**：支持通过 RJ ID 精确查找作品
- **多语言版本**：支持点击其他语言版本 ID 快速切换显示
- **搜索框标签芯片**：标签/关键词/厂商搜索时搜索框内显示独立芯片，每个带 ✕ 按钮可单独关闭

### AI 翻译
- **AI 标题翻译**：支持使用 OpenAI 兼容 API（如 DeepSeek、GPT 等）翻译作品标题
- **思考模式**：支持 DeepSeek 思考模式（`thinking` + `reasoning_effort`），翻译更准确但响应更慢，可在设置中开关（默认开启）
- **翻译按钮**：列表中复制按钮旁显示"翻译"按钮，一键翻译当前作品标题
- **标题切换**：翻译完成后标题旁显示"原/译"切换按钮，随时在原文和译文之间切换
- **翻译持久化**：翻译结果保存到数据库，重启后仍然生效
- **下载使用译文**：当标题显示为译文时，下载目录名自动使用译文标题
- **详情页翻译**：详情页自动显示翻译标题，支持"原/译"切换
- **API 可配置**：设置窗口支持配置 API Key、API 地址、模型名称、思考模式开关

### 作品展示
- **详细信息展示**：点击作品可查看标题、标签、封面、声优、厂商等详细信息
- **Canvas 彩色标签**：列表和详情标签使用 Canvas 绘制 8 色循环彩色标签块，更显眼更流畅
- **封面双尺寸**：列表缩略图 180×180，详情页高清 400×400（异步加载 mainCoverUrl）
- **详情滚动**：详情面板支持滚动条和鼠标滚轮，信息超出时可滚动查看
- **懒加载补充**：缓存作品缺少声优、厂商等信息时自动从 API 补充
- **声优/厂商数据库缓存**：懒加载前先查询本地数据库，命中则跳过 API 请求

### 下载管理
- **全局下载管理器**：`DownloadManager` 单例统一管理所有下载任务，不依赖窗口生命周期
- **下载队列模式**：支持队列模式，作品按顺序下载，避免并发触发限流
- **文件完整性检查**：下载前通过 HEAD 请求获取远程文件大小，与本地对比判断是否完整，不完整会重新下载
- **多作品并行下载**：同时下载多个作品，底部实时显示每个任务的进度
- **提交即返回**：点击下载后立即返回，Aria2 提交和封面下载在后台静默执行
- **后台杂物处理**：封面下载、标签保存、历史写入在后台线程执行，不阻塞任何操作
- **下载窗口瘦身**：下载窗口只负责浏览文件和提交任务，不再管理进度轮询
- **Aria2 集成**：通过 XML-RPC 控制 Aria2 下载，下载时自动检测并启动 Aria2 进程
- **直接下载**：支持不依赖 Aria2 的 HTTP 直接下载，可在设置中切换
- **下载失败重试**：下载失败（429 限流等）自动重试，最多 3 次，指数退避等待
- **真实进度显示**：全局轮询实时进度，底部显示每个任务的进度条、百分比、速度
- **下载历史**：记录已下载作品，支持分页浏览和多种排序
- **下载作品列表**：下拉框"下载作品"tab 直接浏览所有已下载作品，支持排序和分页，切换 tab 时自动缓存避免重复查询，支持"扫描关联"批量获取多语言版本信息
- **懒下载标记**：点击下载即标记已下载状态，无需等待任务提交完成
- **文件名字符过滤**：设置窗口支持自定义额外过滤字符（如 `【】「」《》…`），与 Windows 非法字符合并处理，避免下载目录名包含特殊字符
- **下载任务持久化**：未完成的下载任务（提交中/下载中/排队中/失败）自动保存到数据库，程序重启后自动恢复，失败任务可点击重试继续下载
- **断点续传**：直接下载模式支持 HTTP Range 断点续传，文件部分下载中断后从断点位置继续，服务端不支持时自动回退从头下载
- **下载管理窗口**：独立窗口查看所有下载任务，分「正在下载」和「已完成」两个区域，支持重试/取消操作，实时进度更新
- **低速自动重启**：下载速度持续低于阈值时自动暂停并重新提交任务（利用断点续传接续），可配置阈值/时长/最大重启次数
- **UI 无闪烁刷新**：下载管理窗口和底部栏均采用增量更新策略，仅在任务列表变化时重建控件，进度更新只改文字值
- **自动标记其他语言版本**：下载作品时自动将其所有其他语言版本标记为已下载，后续发现新版本时也会自动标记
- **VTT 字幕自动转换**：下载完成后自动扫描目录下的 VTT 字幕文件并转换为 LRC 格式（支持 UTF-8/Shift-JIS 编码），自动去除 `.mp3`/`.wav`/`.flac` 等音频后缀，转换后自动删除原 VTT 文件，可在设置中开关
- **字幕转换状态**：字幕转换期间显示「字幕转换中」状态，转换完成后再标记为已完成
- **文件夹自动整理**：所有下载任务全部完成后，自动将多层嵌套子文件夹扁平化，只保留最后一层，移动失败自动重试 3 次
- **下载失败自动重试**：直接下载模式下部分文件失败时自动重试（最多 3 次），全部成功后才标记完成
- **进度条线程安全**：进度更新通过主线程调度，避免 UI 崩溃；支持一位小数显示（如 45.3%）
- **底部进度框动态显隐**：底部下载任务进度框仅在有活跃下载任务时显示，无任务时自动隐藏
- **多语言版本关联标记**：列表卡片和详情面板中其他语言版本标签显示下载状态（绿色 ✓ 表示已下载），已下载 Tab 支持批量扫描关联

### 性能优化
- **数据库连接超时管理**：连接 5 分钟未使用自动关闭，启用 WAL 模式提升并发性能 2-3 倍，自动事务管理（commit/rollback）
- **LRU 缓存优化**：使用 `RLock()` 可重入锁 + 超时机制（10ms/20ms），缓存命中率 >95%，添加命中率统计监控
- **内存泄漏防护**：下载任务字典上限 200 个，已完成任务保留最近 100 条，定期清理（每10次轮询或5分钟），支持 7x24 小时稳定运行
- **查询性能优化**：明确指定列名消除 `SELECT *` 和运行时检查，安全 JSON 解析，SQL 注入防护
- **UI 批量更新**：数据加载后合并多次重绘为单次操作，添加等待光标反馈，消除界面闪烁
- **图片智能预加载**：滚动列表时预加载前后各 3 张图片（后台线程 + 队列管理），用户体验接近原生应用
- **缓存效率监控**：实时显示命中率、磁盘大小、内存使用等指标
- **图片两级缓存**：内存 LRU 缓存 + 磁盘 JPEG 缓存，加快图片加载速度
- **磁盘缓存管理**：图片缓存超 500MB 自动清理最旧文件，防止磁盘占满
- **API 请求缓存**：搜索和列表结果自动缓存 120 秒，减少重复网络请求
- **请求合并去重**：相同 API 请求自动合并，避免重复网络请求
- **Session 连接复用**：所有 HTTP 请求使用 `requests.Session` 复用 TCP 连接
- **数据库连接池**：`threading.local()` 缓存每线程数据库连接
- **数据库索引**：关键字段建立索引，查询性能优化
- **控件池复用**：翻页和任务列表更新时复用已有控件，绝不销毁重建
- **搜索框控件复用**：标签/关键词/厂商搜索时复用已有芯片控件，减少闪烁
- **内存排序**：排序切换在内存中完成，毫秒级响应
- **翻页防抖**：快速连点翻页时 300ms 防抖，避免堆积卡顿
- **懒加载去抖**：详情面板信息 300ms 延迟加载，快速切换时自动取消
- **网络重试**：API 请求自动重试（最多 3 次，指数退避）
- **配置容错**：配置文件损坏或缺失时自动使用默认值，应用不崩溃

### 用户体验
- **快捷键支持**：`Ctrl+F` 聚焦搜索框、`←/→` 翻页、`Esc` 清除搜索
- **ID 复制**：点击列表中的复制按钮快速复制 RJ ID
- **标题复制**：详情页复制按钮一键复制当前显示的标题（支持原文/译文）
- **统一滚轮**：左侧列表和右侧详情面板均支持鼠标滚轮滚动
- **模态窗口**：下载窗口和设置窗口以模态方式显示
- **加载进度条**：使用原生 Progressbar 显示加载状态
- **已下载计数**：顶部工具栏实时显示已下载作品总数
- **数据库路径自定义**：设置窗口支持自定义数据库存储位置（支持迁移旧数据）
- **缓存管理**：设置窗口显示图片缓存大小，支持一键清除缓存
- **平滑翻页按钮**：翻页按钮始终显示，在第一页/最后一页时变为禁用状态，位置不跳动
- **动态排序控件**：排序下拉框仅在"下载作品"模式下显示，界面更简洁

## 项目结构

- `src/ui/detail_mixin.py` / `src/ui/detail_actions.py` — 详情面板（展示、滚动、懒加载、CV/厂商显示）+ 操作（隐藏、刷新、删除、复制）
- `src/ui/list_mixin.py` / `src/ui/list_card.py` — 作品列表（缩略图加载、加载动画、滚动、canvas管理）+ 卡片（创建、标签渲染、AI翻译交互）
- `src/ui/search_mixin.py` — 统一搜索（ID/标签/关键词、搜索框标签芯片）
- `src/ui/filter_mixin.py` — 筛选排序（只看已下载、内存排序、封面补全）
- `src/gui_app_ui.py` / `src/gui_app_nav.py` / `src/gui_app_events.py` — 主窗口 Mixin（`UISetupMixin` 样式/UI构建、`NavigationMixin` 数据加载/分页、`EventMixin` 搜索历史/快捷键）
- `src/download/manager.py` / `src/download/manager_core.py` / `src/download/manager_poll.py` / `src/download/models.py` — 全局下载管理器（单例、提交/持久化/队列、轮询进度/重试/低速检测、数据模型）
- `src/services/translator.py` — AI 翻译服务（OpenAI 兼容 API、翻译缓存）
- 通过 Mixin 多继承组合到 WorkApp，MRO：`WorkApp > DetailMixin(DetailActionsMixin) > ListMixin(ListCardMixin) > SearchMixin > FilterMixin > UISetupMixin > NavigationMixin > EventMixin`

```
g:\code\音声下载\
├── src/gui_app.py              # 主程序入口（Mixin模式组合，核心类 + 工具方法）
├── src/gui_app_ui.py           # UISetupMixin（样式配置、UI构建、下载任务显示）
├── src/gui_app_nav.py          # NavigationMixin（数据加载、分页导航、按钮状态管理）
├── src/gui_app_events.py       # EventMixin（搜索历史、键盘快捷键、鼠标滚轮事件）
├── src/                        # 核心业务模块包
│   ├── __init__.py             # 统一导出
│   ├── config.py               # 配置读取（带默认值容错）
│   ├── api_client.py           # API 请求客户端（带指数退避重试 + 缓存去重）
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py         # DatabaseManager（作品缓存、翻译记录、数据库索引）
│   │   ├── history.py          # DownloadHistoryManager（下载历史、作品详情更新、翻译标题）
│   │   ├── pending.py          # PendingTaskManager（下载任务持久化、恢复）
│   │   └── cache.py            # 图片缓存（LRU内存+磁盘两级缓存）
│   ├── download/
│   │   ├── __init__.py
│   │   ├── models.py           # 数据模型（TaskStatus枚举、DownloadTask数据类）
│   │   ├── downloader.py       # Aria2 下载管理（异步下载、连接复用、进度查询）
│   │   ├── downloader_direct.py # 直接下载模块（HTTP 下载，不依赖 Aria2）
│   │   ├── manager.py          # DownloadManager 主类（单例、初始化、队列、取消、重试）
│   │   ├── manager_core.py     # DownloadCoreMixin（下载提交、持久化、队列处理）
│   │   └── manager_poll.py     # DownloadPollMixin（轮询进度、重试、低速自重启）
│   ├── services/
│   │   ├── __init__.py
│   │   └── translator.py       # AI 翻译服务（OpenAI 兼容 API、翻译缓存）
│   └── ui/
│       ├── __init__.py
│       ├── detail_mixin.py     # DetailMixin（详情面板构建、展示、懒加载）
│       ├── detail_actions.py   # DetailActionsMixin（隐藏作品、刷新信息、删除记录、复制）
│       ├── list_mixin.py       # ListMixin（列表展示管理、缩略图加载、canvas滚动）
│       ├── list_card.py        # ListCardMixin（卡片创建、标签Canvas渲染、AI翻译交互）
│       ├── search_mixin.py     # 搜索逻辑（ID/标签/关键词/厂商、搜索框芯片）
│       ├── filter_mixin.py     # 筛选排序（已下载、内存排序、封面补全）
│       ├── gui_download.py     # 下载窗口（树形选择、提交即返回、译文标题）
│       ├── gui_settings.py     # 设置窗口（含缓存管理、数据库路径自定义、AI翻译设置）
│       ├── gui_download_manager.py # 下载管理窗口（正在下载/已完成、重试/取消、进度更新）
│       └── tree_selector.py    # 树状图选择工具类
├── settings/                   # 配置和数据库目录（默认位置）
│   ├── config.json             # JSON 配置文件
│   ├── works.db                # SQLite 数据库文件（作品缓存）
│   ├── download_history.db     # SQLite 数据库文件（下载历史）
│   └── ui.ico                  # 程序图标
├── image_cache/                # 图片缓存目录
├── downloads/                  # 下载文件保存目录（可配置）
└── aria2/                      # Aria2 下载工具目录
    ├── aria2.exe
    ├── aria2c.exe
    ├── aria2.conf
    └── aria2.session
```

## 环境依赖

- Python 3.10+
- tkinter (Python 内置)
- requests
- Pillow

安装依赖：

```bash
pip install requests Pillow
```

## 运行方式

```bash
python src/gui_app.py
```

## 导入本地下载记录

如果已有下载的音声文件，可以导入到数据库以标记为"已下载"状态：

```bash
python import_downloaded.py
```

脚本会读取 `Z:\hhh\asmr\双语` 目录下的文件夹，从文件夹名提取 RJ ID 并导入数据库。

## 主要模块

### src/api_client.py
API 请求客户端，负责与服务器通信，所有请求支持指数退避重试：
- 内置 LRU 结果缓存（最多 100 条，TTL 120 秒），搜索和列表结果自动缓存
- 使用 `requests.Session` 复用 TCP 连接，减少握手开销
- `fetch_works_page(page)` - 获取推荐作品列表分页
- `fetch_latest_works_page(page)` - 获取最新收录作品列表
- `fetch_work_detail(rj_id)` - 获取单个作品详情（自动处理前导零）
- `fetch_tracks(rj_id)` - 获取作品文件列表
- `search_by_tag(tags, page)` - 按标签搜索作品（支持多标签 AND 搜索）
- `search_by_keyword(keyword, page)` - 按关键词模糊搜索
- `search_by_circle(circle_name, page)` - 按厂商名称搜索作品
- `clear_api_cache()` - 清除 API 结果缓存

### src/database/cache.py
图片缓存管理器，实现两级缓存策略：
- **内存缓存**：LRU 策略，最多保存 100 张图片（按尺寸独立缓存：180×180 缩略图 + 400×400 高清图）
- **磁盘缓存**：保存到 `image_cache` 目录，JPEG 85% 质量压缩
- **磁盘清理**：缓存超过 500MB 自动删除最旧文件
- `get(url)` / `get_thumbnail(url)` - 获取 180×180 缩略图
- `get_at_size(url, size)` - 获取指定尺寸图片（如 400×400 高清）
- `load_from_url(url, size)` - 从 URL 加载并缓存指定尺寸图片
- `get_http_session()` - 获取线程本地 requests.Session（连接复用）

### src/database/
数据库管理模块（拆分为 3 个文件），所有操作使用 `contextmanager` 确保连接安全关闭：

- **database.py** — `DatabaseManager`：作品缓存管理、翻译记录存储、分页数据、数据库索引
- **history.py** — `DownloadHistoryManager`：下载历史记录、作品详情更新（声优/厂商/封面）、下载作品查询、翻译标题存取
- **pending.py** — `PendingTaskManager`：下载任务持久化（提交中/下载中/排队中/失败）、启动恢复、状态同步

### src/download/downloader.py
下载管理模块，负责：
- 通过 Aria2 下载文件（异步执行，连接复用）
- 保存封面图片和标签文件
- 管理下载历史
- `poll_download_progress(gids)` - 轮询 Aria2 真实下载进度
- `ensure_aria2_running()` - 下载时自动检测并启动 Aria2
- `purge_aria2_downloads()` - 清除 Aria2 下载结果缓存

### src/download/downloader_direct.py
直接下载模块，不依赖 Aria2：
- 使用 requests 直接 HTTP 下载文件
- 支持断点续传和进度显示
- 429 限流自动重试（最多 5 次，指数退避）
- `DirectDownloader` - 直接下载器类
- `poll_direct_progress(task_ids)` - 轮询直接下载进度

### src/download/manager.py + manager_core.py + manager_poll.py + models.py
全局下载管理器（线程安全单例），拆分为 4 个文件，核心调度层：

- **models.py** — `TaskStatus`（任务状态枚举：submitting/downloading/completed/failed/cancelled/queued）、`DownloadTask`（数据模型：work_id/gids/进度/状态/速度）
- **manager.py** — `DownloadManager` 主类（单例）：初始化、`submit(work, files)` 提交即返回、`cancel/retry` 取消/重试、`get_all_tasks/get_active_tasks` 查询、`restore_pending_tasks` 恢复持久化任务、`add_observer` 观察者模式通知
- **manager_core.py** — `DownloadCoreMixin`：Aria2/直接下载提交逻辑、文件完整性检查（跳过已完整文件）、任务持久化/状态同步、队列模式处理
- **manager_poll.py** — `DownloadPollMixin`：全局统一轮询循环（有任务自动启动/全完成自动退出）、Aria2/直接下载进度合并、失败自动重试（最多 3 次）、低速检测与自动重启（可配置阈值/时长/次数）

### src/ui/tree_selector.py
树状图选择工具类，提供：
- `select_all()` - 全选所有节点
- `deselect_all()` - 取消所有选中
- `select_all_in_folder(folder_id)` - 全选文件夹内所有内容
- `get_selected_leaf_items()` - 获取选中的叶子节点（文件）
- `invert_selection()` - 反选所有节点
- `expand_all()` / `collapse_all()` - 展开/折叠所有节点

### WorkApp (src/gui_app.py + src/gui_app_ui.py + src/gui_app_nav.py + src/gui_app_events.py)
主应用程序类，通过 Mixin 多继承组合功能模块（拆分为 4 个文件，总行数从 891 行降至各文件均 ≤ 366 行）：

- **src/gui_app.py**（272行）— `WorkApp` 类声明、`__init__` 初始化所有组件、工具方法（`_format_size`、`_format_speed`、`copy_to_clipboard`）、`main` 入口
- **src/gui_app_ui.py**（226行）— `UISetupMixin`：`_setup_styles()` 全局样式、`setup_ui()` 全部控件构建、`_create_task_slot()`/`_refresh_task_display()` 下载任务显示、`open_settings()`/`open_download_manager()` 窗口管理
- **src/gui_app_nav.py**（363行）— `NavigationMixin`：`load_data_async()` 异步数据加载、`_on_tab_changed()` 列表切换、`go_to_page()`/`prev_page()`/`next_page()` 分页导航、`update_buttons()` 按钮状态、`refresh_data()` 数据刷新
- **src/gui_app_events.py**（142行）— `EventMixin`：`_push_search_history()`/`go_back_search()` 搜索历史导航、`_bind_shortcuts()` 全局快捷键绑定、`_on_mouse_wheel()` 滚轮事件、`_on_escape()` ESC 清除搜索

Mixin 继承链（MRO 从左到右，深度优先）：
```
WorkApp > DetailMixin(DetailActionsMixin) > ListMixin(ListCardMixin) > SearchMixin > FilterMixin > UISetupMixin > NavigationMixin > EventMixin
```

## 界面说明

- **顶部导航栏**：列表切换（推荐作品/最新收录/下载作品）、刷新按钮、统一搜索框（支持文本输入、标签芯片、厂商芯片显示）、排序下拉框
- **左侧列表区**：显示作品缩略图、标题、Canvas 彩色标签、ID复制按钮和下载状态
- **右侧详情区**：显示选中作品的完整信息，厂商名可点击搜索
- **底部导航栏**：上一页/下一页按钮、页码跳转、设置按钮

## 列表切换

支持三个数据源：
1. **推荐作品**：基于推荐算法的作品列表
2. **最新收录**：按收录时间排序的最新作品
3. **下载作品**：已下载的作品列表（支持排序和分页，切换 tab 自动缓存）

## 筛选功能

切换下拉框"下载作品"tab 即可浏览所有已下载作品（支持排序和分页）。

### 排序选项（仅"下载作品"模式）
- 下载时间最新
- 下载时间最旧
- 标题 A-Z / Z-A
- ID 从小到大 / 从大到小

## API 信息

- **推荐列表接口**：`https://api.asmr-200.com/api/recommender/recommend-for-user`
- **最新收录接口**：`https://api.asmr-200.com/api/works`
- **作品详情接口**：`https://api.asmr-200.com/api/workInfo/{id}`
- **标签搜索接口**：`https://api.asmr-200.com/api/search/{encoded_tag}`
- **厂商搜索接口**：`https://api.asmr-200.com/api/search/{$circle:NAME$}`
- **请求方式**：POST（推荐列表）、GET（最新收录、详情、标签搜索、厂商搜索）
- **数据格式**：JSON

## RJ ID 格式说明

系统内部统一使用 `RJ` + 6位数字格式（如 `RJ010101`），会自动规范化比较：
- `RJ10101` → `RJ010101`
- `rj010101` → `RJ010101`
- `RG010101` → `RJ010101`

## 下载功能

下载架构由全局 `DownloadManager`（单例）统一管理，下载窗口仅负责文件选择和提交。

### 下载流程

1. **打开下载窗口** → 浏览作品文件树
2. **选择文件** → 全选 / 逐项勾选 / 双击文件夹全选
3. **点击下载** → 立即提交到 `DownloadManager`，窗口 2 秒后自动关闭
4. **后台执行**：
   - 创建以 `RJ号-标题` 命名的文件夹
   - 逐一调用 Aria2 XML-RPC 提交所有文件下载
   - 下载封面图片保存为 `封面.jpg`
   - 保存标签到 `标签.txt`
5. **实时进度**：主界面底部显示所有进行中任务的进度条、百分比、实时速度

### 架构优势

| 特性 | 旧架构 | 新架构（v1.17.0） |
|------|--------|-------------------|
| 任务管理 | 窗口内持有 GID，关闭时转移 | `DownloadManager` 全局单例统一管理 |
| 轮询方式 | 每个窗口独立轮询 | 全局统一轮询线程，自动启停 |
| 多作品支持 | 仅支持单作品下载 | 多作品并行下载 |
| 窗口关闭 | 需要转移轮询，逻辑复杂 | 提交后即可关闭，无耦合 |
| 底部进度 | 单一进度条，仅显示一个 | 任务列表，显示多个作品进度 |
| 封面/标签 | 阻塞下载流程 | 后台 Housekeeper 静默执行 |

### 下载窗口操作
- **双击文件夹**：选中文件夹内的所有文件
- **全选按钮**：选中所有根项目
- **取消全选按钮**：取消所有选择
- **下载选中**：提交选中的文件到全局下载队列

### Aria2 按需启动

下载时自动检测 Aria2 是否在线，未运行则自动启动：
- 默认 RPC 地址：`http://localhost:6800/rpc`
- 配置文件：`aria2/aria2.conf`
- 如果端口 6800 被占用，说明 Aria2 已在运行
- 启动失败时会自动重试（最多 20 次，每次 0.5 秒）

这些设置可通过 `settings/config.json` 进行修改。

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+F` | 聚焦搜索框 |
| `←` / `→` | 上一页 / 下一页（搜索框内输入时不触发） |
| `Up` / `Down` | 上一个作品 / 下一个作品（列表区导航，右侧详情同步更新） |
| `PageUp` / `PageDown` | 上一页 / 下一页 |
| `Ctrl+D` / `Enter` | 打开当前选中作品的下载窗口（搜索框内输入时不触发） |
| `Esc` | 清除搜索状态（搜索框失去焦点、清除标签/关键词） |

## 设置与缓存管理

点击底部导航栏的"设置"按钮打开设置窗口：

- **下载方式**：选择使用 Aria2 或直接下载（HTTP）
  - Aria2：功能强大，支持断点续传、多连接下载
  - 直接下载：不依赖外部程序，适合 Aria2 受限的环境
- **Aria2 RPC 地址**：设置 Aria2 XML-RPC 连接地址
- **直接下载线程数**：设置直接下载的并发线程数（1-10）
- **下载队列**：
  - **启用队列模式**：勾选后作品按顺序下载，一个完成后再开始下一个
  - **最大同时下载数**：设置队列模式下同时下载的作品数（1-5）
- **下载目录**：设置下载文件保存目录
- **文件名过滤字符**：填写需要额外过滤的字符（如 `【】「」《》…`），这些字符会从下载文件夹名中移除。留空则仅过滤 Windows 非法字符（`\/:*?"<>|`）
- **数据库目录**：自定义数据库文件（works.db / download_history.db）存储位置，留空使用默认 `settings/` 目录。路径变更时自动复制旧数据库文件到新位置，提示重启后生效。翻译结果存储在 works.db 的 `translations` 表中
- **图片缓存**：显示当前缓存大小，点击"清除缓存"一键清理（同时清除内存缓存和磁盘缓存文件）
- **AI 翻译设置**：
  - **启用 AI 翻译**：勾选后开启翻译功能，列表中显示翻译按钮
  - **API Key**：填写 OpenAI 兼容 API 的密钥（如 DeepSeek、GPT 等）
  - **API 地址**：填写 API 基础地址（如 `https://api.deepseek.com/v1`）
  - **模型名称**：填写使用的模型（如 `deepseek-chat`、`gpt-3.5-turbo`）
  - **思考模式**：启用 DeepSeek 思考模式（翻译更准确但响应更慢），默认开启；开启后翻译请求超时自动放宽至 90 秒

## 已知问题与改进计划

历史修复和优化记录已迁移至 [CHANGELOG.md](CHANGELOG.md)。

### 待优化
- **虚拟滚动**：只渲染可见区域的列表项

### 🏗️ 架构改进方案

#### 模块化重构
```
src/
├── core/                    # 核心业务逻辑
│   ├── services/           # 服务层
│   │   ├── api_service.py  # API 服务
│   │   ├── db_service.py   # 数据库服务
│   │   └── cache_service.py # 缓存服务
│   ├── models/             # 数据模型
│   │   ├── work.py         # 作品模型
│   │   └── download.py     # 下载模型
│   └── utils/              # 工具类
├── ui/                      # 用户界面
│   ├── views/              # 视图层
│   ├── components/         # 可复用组件
│   └── styles/             # 样式配置
└── data/                    # 数据层
    ├── repositories/       # 数据仓库
    └── cache/              # 缓存策略
```

#### 依赖注入
```python
# 建议使用依赖注入减少耦合
class ServiceContainer:
    def __init__(self):
        self._services = {}
        
    def register(self, name, service):
        self._services[name] = service
        
    def get(self, name):
        return self._services.get(name)

# 使用示例
container = ServiceContainer()
container.register('api_client', APIClient())
container.register('database', DatabaseManager())
```

#### 事件驱动架构
```python
# 建议实现事件总线
class EventBus:
    def __init__(self):
        self._listeners = {}
        
    def on(self, event_type, callback):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
        
    def emit(self, event_type, data=None):
        for callback in self._listeners.get(event_type, []):
            callback(data)
```

### 🎨 用户体验改进

#### 界面响应性
- **添加加载状态**：所有长时间操作显示进度条
- **实现骨架屏**：数据加载时显示占位符
- **优化滚动性能**：实现虚拟滚动，只渲染可见区域
- **添加动画效果**：平滑过渡动画提升用户体验

#### 错误处理增强
```python
# 建议统一错误处理
class ErrorHandler:
    @staticmethod
    def handle(error, context=""):
        error_types = {
            "network": "网络连接失败，请检查网络设置",
            "api": "API请求失败，请稍后重试",
            "database": "数据库错误，请重启应用",
            "permission": "权限不足，请检查文件权限"
        }
        
        user_message = error_types.get(type(error).__name__, "发生未知错误")
        # 记录详细错误信息
        logging.error(f"{context}: {error}")
        # 显示用户友好提示
        show_error_dialog(user_message)
```

#### 功能增强建议
1. **下载队列管理**
   - 支持暂停、继续下载
   - 下载优先级调整
   - 下载顺序调整
   - 批量删除下载任务

2. **搜索历史**
   - 记录搜索历史
   - 显示热门搜索
   - 搜索建议功能
   - 清除搜索历史

3. **批量操作**
   - 批量选择作品
   - 批量删除下载记录
   - 批量导出信息
   - 批量下载

4. **快捷键支持**（v1.34.0 已全面实现）
   - ~~`Ctrl+F`：聚焦搜索框~~
   - ~~`←/→`：翻页~~
   - ~~`Enter`：确认搜索/打开下载~~
   - ~~`Esc`：取消当前操作~~
   - ~~`Ctrl+D`：下载选中作品~~
   - ~~`Up/Down`：切换列表选中作品~~
   - ~~`PageUp/PageDown`：翻页~~

5. **主题切换**
   - 支持明暗主题切换
   - 自定义主题颜色
   - 字体大小调整
   - 界面缩放

6. **数据导出**
   - 导出下载历史为 CSV/JSON
   - 导出作品信息
   - 导出标签数据
   - 备份/恢复配置

### 🔧 代码质量改进

#### 类型注解
```python
# 建议添加类型注解
from typing import List, Dict, Optional, Tuple

def fetch_works_page(self, page: int, page_size: int = 20) -> Tuple[List[Dict], int]:
    """获取作品分页数据
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        (作品列表, 最大页数)
    """
    pass
```

#### 单元测试
```python
# 建议添加单元测试
import unittest

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")
        
    def test_save_and_get_works(self):
        works = [{"id": "1", "title": "Test"}]
        self.db.save_works(works, 1)
        result = self.db.get_works_by_page(1)
        self.assertEqual(len(result), 1)
        
    def test_normalize_rj_id(self):
        db = DownloadHistoryManager(":memory:")
        self.assertEqual(db._normalize_rj_id("RJ12345"), "012345")
        self.assertEqual(db._normalize_rj_id("rj12345"), "012345")
```

#### 日志系统
```python
# 建议实现结构化日志
import logging
from datetime import datetime

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
    def log(self, level, message, **kwargs):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        self.logger.log(level, json.dumps(log_entry, ensure_ascii=False))
```

#### 代码规范
- 使用 `pylint` 或 `flake8` 进行代码检查
- 统一代码风格（建议使用 `black` 格式化）
- 添加类型检查（使用 `mypy`）
- 定期进行代码审查

#### 待实现
1. 虚拟滚动优化
2. 主题切换功能

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)
