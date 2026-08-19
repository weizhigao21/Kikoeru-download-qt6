﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿# 音声作品浏览下载

一个基于 Qt6（PyQt6）的桌面应用程序，用于浏览和下载 ASMR 音声作品。

**GitHub 仓库**：https://github.com/weizhigao21/Kikoeru-download-qt6

## 版本

**v2.2.2**（当前版本，Qt6 UI）

## 功能特性

### 浏览与搜索
- **四列表浏览**：支持"推荐作品"、"最新收录"、"下载作品"和"没有下载"四个数据源切换
- **没有下载 tab**（v2.1.0）：新增第 4 个 tab「没有下载」，展示数据库中所有未下载的作品（其他语言版本复用卡片紫色可点击标签），按**发售日期**倒序排列（最新发售在前）
- **自动采集**（v2.1.0）：后台每 3s 自动采集「最新收录」作品入本地库，头部追新（第 1 页有新作品优先入库）+ 游标补历史双轨调度；递增步长跳页快速跨历史区，回退锁定避免跳页漏边界；采集游标持久化到数据库，断点续扫、跨天计数归零但游标保持；每日入库上限兜底不冲击服务器
- **分页浏览**：支持按页查看作品列表，每页显示 20 个作品
- **隐藏下载作品**：在"推荐作品"和"最新收录"模式下，点击按钮切换"显示全部/隐藏下载"状态，快速过滤已下载作品
- **标签搜索**：点击任意标签快速筛选同类作品，支持多标签组合搜索（AND 交集），每个标签可单独移除
- **关键词搜索**：统一搜索框，自动识别输入为 RJ ID 或关键词进行模糊搜索
- **厂商搜索**：点击详情页厂商名称搜索该厂商的所有作品，顶栏显示粉色「厂商: xxx」chip（带 ✕ 可移除），可与标签 chip 共存组合过滤
- **ID 搜索**：支持通过 RJ ID 精确查找作品
- **多语言版本**：支持点击其他语言版本 ID 快速切换显示
- **标签搜索芯片**：点击标签后搜索框替换为彩色标签 chip（色池循环上色、悬停加深，每个带 ✕ 按钮可单独移除），支持多标签累积搜索；厂商 chip 与标签 chips 可并排共存，实现「厂商 + 标签」组合搜索
- **下载作品本地搜索**：在「下载作品」tab 内点击标签/厂商或关键词搜索直接走本地数据库过滤（不请求 API），切换到「最新/推荐」tab 才走 API 搜索
- **切换保留搜索条件**：切换 tab 后之前的标签/厂商/关键词搜索条件与 chips 保留，自动用同一条件在新 tab 继续搜索
- **滚动位置重置**（v2.0.6）：翻页/搜索/刷新后列表滚动条自动回到顶部；详情刷新 / 隐藏作品 / 删除记录 / 「没有下载」页自动刷新（下载完成 / 新数据入库）等局部操作保持当前滚动位置与详情面板（`WorksListView.set_works(works, scroll_to_top)` 统一入口按场景控制）

### AI 翻译
- **AI 标题翻译**：支持使用 OpenAI 兼容 API（如 DeepSeek、GPT 等）翻译作品标题
- **思考模式**：支持 DeepSeek 思考模式（`thinking` + `reasoning_effort`），翻译更准确但响应更慢，可在设置中开关（默认开启）
- **翻译按钮**：列表中复制按钮旁显示"翻译"按钮，一键翻译当前作品标题
- **右键翻译菜单**（v2.0.0）：列表右键作品弹出「翻译」子菜单，支持翻译标题 / 编辑翻译 / 重新翻译 / 删除翻译
- **翻译缓存显示**（v2.0.0）：翻页/搜索后列表卡片直接显示已缓存的译文
- **标题切换**：翻译完成后标题旁显示"原/译"切换按钮，随时在原文和译文之间切换
- **翻译持久化**：翻译结果保存到数据库，重启后仍然生效
- **下载使用译文**：当标题显示为译文时，下载目录名自动使用译文标题
- **详情页翻译**：详情页自动显示翻译标题，支持"原/译"切换
- **API 可配置**：设置窗口支持配置 API Key、API 地址、模型名称、思考模式开关
- **翻译结果健壮性**（v2.1.2）：强化提示词（禁止解释/代码块/JSON/引号，不得拒绝翻译）；自动清洗模型输出（剥 Markdown 代码块、JSON 包裹、成对引号、「以下是翻译结果：」等前缀）；思考模式下 `content` 为空时自动从 `reasoning_content` 提取译文，仍为空则自动降级为普通模式重试一次
- **词义拆解**（v2.2.0）：详情面板标题行新增「拆解」按钮，对日文原题生成逐词拆解（自造词/拟声拟态词/专有名词/古语/口语拉长音，自造词拆词源）+ 末尾「整体理解」，弹窗展示可复制；独立入口与纯译文链路分离，缓存与数据库持久化（translations 表 `title_explanation` 列），删除翻译时同步删除
- **翻译上下文自定义**（v2.2.1）：设置 → AI 翻译页新增「翻译上下文 / 风格提示」多行文本框（默认预填推荐上下文：DLsite 标题术语惯例、保留 ♡～ 等装饰符号、语气贴近原题、自造词音译），翻译请求时注入 system prompt 提升翻译质量；清空 = 不注入，拆解请求不受影响
- **翻译提示词完全自定义**（v2.2.2）：设置里的文本框即完整 System Prompt，翻译请求**不再拼接内置规则**，完全按用户提示词执行（解决内置"只输出译文"规则与自定义格式要求冲突的问题）；清空 = 回退内置默认规则

### 作品展示
- **详细信息展示**：点击作品可查看标题、标签、封面、声优、厂商等详细信息
- **彩色标签**：列表卡片与详情面板标签使用色池循环绘制彩色圆角标签块（QPainter 全绘制 / FlowTags 布局），更显眼更流畅，点击标签可搜索
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
- **文件列表本地缓存**：双击作品打开的文件树持久化到本地数据库，再次打开同一作品秒级加载、无需重复请求 API；支持手动"刷新"按钮强制更新
- **Aria2 集成**：通过 XML-RPC 控制 Aria2 下载，下载时自动检测并启动 Aria2 进程
- **直接下载**：支持不依赖 Aria2 的 HTTP 直接下载，可在设置中切换
- **下载失败重试**：下载失败（429 限流等）自动重试，最多 3 次，指数退避等待
- **真实进度显示**（v2.0.7 落地）：全局轮询实时进度，底部任务条显示每个活跃任务的进度条、百分比、速度，任务集合变化时重建、进度变化只改值，无任务自动隐藏
- **下载历史**：记录已下载作品，支持分页浏览和多种排序
- **下载作品列表**：下拉框"下载作品"tab 直接浏览所有已下载作品，支持排序和分页，切换 tab 时自动缓存避免重复查询（v2.0.7：同排序缓存生效，删除记录/下载完成/刷新时自动失效），支持"扫描关联"批量获取多语言版本信息
- **懒下载标记**：点击下载即标记已下载状态，无需等待任务提交完成
- **文件名字符过滤**：设置窗口支持自定义额外过滤字符（如 `【】「」《》…`），与 Windows 非法字符合并处理，避免下载目录名包含特殊字符
- **目录名标题长度可配置**（v2.0.8）：下载文件夹名中的标题最大长度可在设置中配置（默认 120 字符，0 不限制），修复原硬编码 50 字符导致长标题被截断的问题；同时补强 Windows 保留设备名/尾部空格/控制字符过滤与路径长度保护
- **下载任务持久化**：未完成的下载任务（提交中/下载中/排队中/失败）自动保存到数据库，程序重启后自动恢复，失败任务可点击重试继续下载
- **断点续传**：直接下载模式支持 HTTP Range 断点续传，文件部分下载中断后从断点位置继续，服务端不支持时自动回退从头下载
- **下载管理窗口**：独立窗口查看所有下载任务，分「正在下载」和「已完成」两个区域，支持重试/取消操作，实时进度更新
- **低速自动重启**：下载速度持续低于阈值时自动暂停并重新提交任务（利用断点续传接续），可配置阈值/时长/最大重启次数
- **UI 无闪烁刷新**（v2.0.7 落地）：下载管理窗口和底部任务条均采用增量更新策略，仅在任务列表变化时重建控件，进度更新只改文字值
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
- **图片异步加载**：列表缩略图由后台线程批量加载（LRU 内存 + 磁盘两级缓存），加载完成信号回主线程更新；v2.0.7 起缩略图 4 线程池并发加载（翻页即取消旧批次），就绪后合并重绘
- **完整性检查并发化**（v2.0.7）：下载前远程文件大小 HEAD 校验并发执行（8 并发），避免逐文件串行网络请求阻塞下载启动；异常时自动回退串行
- **退出线程安全**（v2.0.7）：关闭窗口时后台线程有限等待，超时自动 detach 自然回收，杜绝 "QThread: Destroyed while thread is still running" 崩溃
- **滚轮平滑滚动**（v2.0.7）：鼠标滚轮离散大跳改为 16ms 分步平滑滚动（每格 ≈0.8 行、每帧 ≤36px），对齐拖动滚动条的增量节奏，消除滚轮滚动卡顿；触控板（像素增量）走 Qt 原生平滑不受影响
- **缓存效率监控**：实时显示命中率、磁盘大小、内存使用等指标
- **图片两级缓存**：内存 LRU 缓存 + 磁盘 JPEG 缓存，加快图片加载速度
- **磁盘缓存管理**：图片缓存超 500MB 自动清理最旧文件，防止磁盘占满
- **API 请求缓存**：搜索和列表结果自动缓存 120 秒，减少重复网络请求
- **请求合并去重**：相同 API 请求自动合并，避免重复网络请求
- **Session 连接复用**：所有 HTTP 请求使用 `requests.Session` 复用 TCP 连接
- **数据库连接池**：`threading.local()` 缓存每线程数据库连接
- **数据库索引**：关键字段建立索引，查询性能优化
- **虚拟列表**：QListView + Delegate 全绘制，仅实例化可见行，滚动流畅且控件数量恒定
- **标签 chip 动态重建**：多标签搜索时顶栏彩色标签 chip 按需重建，每个带 ✕ 可单独移除
- **内存排序**：排序切换在内存中完成，毫秒级响应
- **generation 过期校验**：翻页/搜索/详情请求带批次号，快速切换时过期请求结果自动丢弃
- **网络重试**：API 请求自动重试（最多 3 次，指数退避）
- **配置容错**：配置文件损坏或缺失时自动使用默认值，应用不崩溃

### 用户体验
- **快捷键支持**：`Ctrl+F` 聚焦搜索框、`←/→` 翻页、`Esc` 清除搜索
- **ID 复制**：点击列表中的复制按钮快速复制 RJ ID
- **标题复制**：详情页复制按钮一键复制当前显示的标题（支持原文/译文）
- **统一滚轮**：左侧列表和右侧详情面板均支持鼠标滚轮滚动
- **模态窗口**：下载窗口和设置窗口以模态方式显示
- **加载状态提示**：数据加载时状态栏显示"加载中..."，完成后显示页码与条数
- **已下载计数**：顶部工具栏实时显示已下载作品总数
- **数据库路径自定义**：设置窗口支持自定义数据库存储位置（支持迁移旧数据）
- **缓存管理**：设置窗口显示图片缓存大小，支持一键清除缓存
- **平滑翻页按钮**：翻页按钮始终显示，在第一页/最后一页时变为禁用状态，位置不跳动
- **动态排序控件**：排序下拉框仅在"下载作品"模式下显示，界面更简洁

## 项目结构

- `src/ui/qt/app.py` — Qt6 应用入口（`QApplication` + `MainWindow` + 全局字体/QSS）
- `src/ui/qt/main_window.py` — 主窗口：导航/翻页/搜索/过滤编排、翻译动作、下载管理接线
- `src/ui/qt/works_list.py` — 列表虚拟化（`WorksListView` + `WorksListModel` + `WorkCardDelegate` 全绘制卡片；`set_works(works, scroll_to_top)` 统一数据入口，翻页回顶/局部刷新保持位置）
- `src/ui/qt/detail_panel.py` — 详情面板（完整字段、FlowTags 圆角标签、可点击厂商、译/原切换）
- `src/ui/qt/top_bar.py` / `bottom_bar.py` — 顶栏（tab/搜索/排序）与底栏（翻页居中/下载管理/设置）
- `src/ui/qt/download_dialog.py` / `download_manager_dialog.py` / `settings_dialog.py` — 三个对话框（文件树/任务列表/设置五页）
- `src/ui/qt/workers.py` — `DataWorker` / `ThumbnailWorker`（QThread + signal/slot 跨线程）
- `src/ui/qt/collector.py` — `NewWorksPoller` 自动采集线程（双轨定时器：头部追新 + 游标补历史，递增步长跳页 + 回退锁定、采集游标持久化、每日上限）
- `src/ui/qt/qt_fonts.py` / `styles.py` — Qt 字体适配层（复用 `src/ui/fonts.py` 常量）与 QSS 样式
- `legacy_tk/` — v2.0.0 归档的 tkinter 版 UI（gui_app*.py 与 src/ui 下 10 个模块）
- `src/download/manager.py` / `src/download/manager_core.py` / `src/download/manager_poll.py` / `src/download/models.py` — 全局下载管理器（单例、提交/持久化/队列、轮询进度/重试/低速检测、数据模型）
- `src/services/translator.py` — AI 翻译服务（OpenAI 兼容 API、线程安全单例、翻译/拆解双缓存、思考模式、词义拆解 explain、`_safe_callback` 异常保护）

```
g:\code\音声下载\
├── app.py                       # 程序入口（python app.py）
├── legacy_tk/                   # tkinter 版 UI 归档（v2.0.0 起不再使用）
├── src/                         # 核心业务模块包
│   ├── __init__.py             # 统一导出
│   ├── config.py               # 配置读取（默认值合并 + 解析错误日志 + 版本号常量）
│   ├── api_client.py           # API 请求客户端（带指数退避重试 + 缓存去重）
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseDatabaseManager（连接复用、close_all 注册表）
│   │   ├── database.py         # DatabaseManager（作品缓存、翻译记录、数据库索引）
│   │   ├── history.py          # DownloadHistoryManager（下载历史、作品详情更新、翻译标题）
│   │   ├── pending.py          # PendingTaskManager（下载任务持久化、恢复）
│   │   ├── tracks.py           # WorkTracksManager（作品文件树持久化缓存）
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
│   │   ├── translator.py          # AI 翻译服务（线程安全单例、翻译/拆解双缓存、思考模式、词义拆解 explain）
│   │   ├── subtitle_converter.py  # VTT→LRC 字幕转换（时间戳进位、NOTE 块空行结束、多编码）
│   │   └── text_converter.py      # 繁简转换（UTF-8/Shift-JIS 回退、文件名+内容转换）
│   └── ui/
│       ├── __init__.py
│       ├── fonts.py             # 字体族常量 + 语义化字体元组（Qt 版复用）
│       └── qt/
│           ├── app.py           # QApplication 入口
│           ├── main_window.py   # MainWindow（导航/搜索/翻译/下载接线）
│           ├── works_list.py    # 列表虚拟化（Model + Delegate 全绘制）
│           ├── detail_panel.py  # 详情面板
│           ├── top_bar.py / bottom_bar.py
│           ├── download_dialog.py / download_manager_dialog.py / settings_dialog.py
│           ├── workers.py       # DataWorker / ThumbnailWorker
│           ├── collector.py     # NewWorksPoller 自动采集线程
│           └── styles.py / qt_fonts.py
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
- PyQt6
- requests
- Pillow
- zhconv（下载完成后繁简转换）

安装依赖：

```bash
pip install PyQt6 requests Pillow zhconv
```

## 运行方式

```bash
python app.py
```

（或 `python -m src.ui.qt.app`）

## 打包发布

**一键打包**：双击运行项目根目录的 `打包.bat` 即可（自动定位 Python 3.10、检查/安装依赖与 PyInstaller、备份旧产物、打包、精简产物、校验 exe），产物为 `dist/音声浏览下载/` 目录（单个 exe + `_internal/` 依赖目录），启动约 1-2 秒出窗口，分发时将整个目录压缩为 zip 发布。

手动打包（PyInstaller onedir 模式）：

```bash
pip install pyinstaller
pyinstaller --noconfirm 音声浏览下载.spec
```

产物约 **87MB**（v2.1.1 起已精简：`spec` 排除 numpy / PyQt6.QtPdf 等未用库，打包后仅保留简体中文 Qt 翻译、删除软件 OpenGL 渲染器 `opengl32sw.dll`；aria2 不再打包）。spec 已配置：入口 `app.py`（Qt6）、`settings\ui.ico` 图标、`console=False`（无控制台窗口）、`optimize=2`、排除 tkinter/pywin32/pythonnet 等未用库。

### 外部资源目录

| 目录 | 用途 | 查找顺序 |
|---|---|---|
| `aria2/` | aria2.exe 等下载工具（**v2.1.1 起不再打包进 exe**，需在 exe 旁放置） | exe 旁 `aria2/`；config.json 的 `aria2_dir` 可指定绝对路径 |
| `settings/` | config.json 配置、works.db / download_history.db 数据库（首次运行自动创建） | exe 旁 `settings/` |
| `downloads/` | 下载作品存放 | exe 旁 `downloads/`，config.json 的 `download_dir` 可指定绝对路径 |

启动优化：v2.0.2 起模块导入瘦身、`ImageTk`/`tkinter` 懒加载、QSplashScreen 启动画面 + 主窗口非关键初始化延迟；v2.0.3 起 onedir 免解压（启动实测约 1.4 秒）+ 外部资源路径回退。

## 主要模块

### src/api_client.py
API 请求客户端，负责与服务器通信，所有请求支持指数退避重试：
- 内置 LRU 结果缓存（最多 100 条，TTL 120 秒），搜索和列表结果自动缓存
- 使用 `requests.Session` 复用 TCP 连接，减少握手开销
- `_InFlight` 并发去重：相同 key 的并发请求只执行一次，等待者复用首个调用者的结果或异常
- 429 限流响应优先读取 `Retry-After` 头（上限 60s），回退到指数退避
- `fetch_works_page(page)` / `fetch_latest_works_page(page)` - 推荐/最新作品列表分页（共用 `_fetch_works_page_impl`）
- `fetch_work_detail(rj_id)` - 获取单个作品详情（`strip_rj_prefix` 处理前缀）
- `fetch_tracks(rj_id)` - 获取作品文件列表
- `search_by_tag(tags, page)` / `search_by_keyword(keyword, page)` / `search_by_circle(circle_name, page)` - 三种搜索共用 `_parse_search_response` + `_search_impl`
- `clear_api_cache()` - 清除 API 结果缓存
- `APIClient(session=None, cache=None)` - 薄封装类，支持依赖注入便于测试

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
- 通过 Aria2 下载文件（异步执行，全局代理复用）
- 保存封面图片和标签文件（封面 ID 解析用 `strip_rj_prefix`）
- 管理下载历史
- `poll_download_progress(gids)` - 轮询 Aria2 真实下载进度
- `ensure_aria2_running()` - 下载时自动检测并启动 Aria2（无 `shell=True`）
- `purge_aria2_downloads()` - 清除 Aria2 下载结果缓存

### src/download/downloader_direct.py
直接下载模块，不依赖 Aria2：
- 使用 requests 直接 HTTP 下载文件
- 支持断点续传和进度显示
- 429 限流自动重试（最多 5 次，优先读 `Retry-After` 头，回退指数退避）
- `get_remote_file_size(url)` - 获取远程文件大小（HEAD 失败回退 GET stream）
- `DirectDownloader` - 直接下载器类
- `poll_direct_progress(task_ids)` - 轮询直接下载进度

### src/download/manager.py + manager_core.py + manager_poll.py + models.py
全局下载管理器（线程安全单例），拆分为 4 个文件，核心调度层：

- **models.py** — `TaskStatus`（任务状态枚举：submitting/downloading/completed/failed/cancelled/queued/converting）、`DownloadTask`（数据模型：work_id/gids/进度/状态/速度）
- **manager.py** — `DownloadManager` 主类（单例）：初始化、`submit(work, files)` 提交即返回（含 CONVERTING 重复防护）、`cancel/retry` 取消/重试、`get_all_tasks/get_active_tasks` 查询、`restore_pending_tasks` 恢复持久化任务、`add_observer` 观察者模式通知
- **manager_core.py** — `DownloadCoreMixin`：Aria2/直接下载提交逻辑、`_check_files_existence`/`_handle_task_completion`/`_safe_persist` 公共方法、队列模式处理
- **manager_poll.py** — `DownloadPollMixin`：全局统一轮询循环（永不退出 + `_poll_wake_event` 唤醒）、Aria2/直接下载进度合并、失败自动重试（最多 3 次）、`_cleanup_and_reset_task` 公共清理方法、低速检测与自动重启（可配置阈值/时长/次数）

> 注：tkinter 版 UI 模块（tree_selector.py、list_card.py、detail_mixin.py 等 10 个文件）已随 v2.0.0 归档至 `legacy_tk/`，详见 CHANGELOG。

### MainWindow (src/ui/qt/main_window.py)
Qt6 主窗口类（v2.0.0），QThread + signal/slot 跨线程，替代 tkinter 版 Mixin 组合：

- **app.py** — `QApplication` 入口（全局字体微软雅黑 UI + QSS 样式 + logging 配置）
- **main_window.py** — `MainWindow`：四 tab 导航、分页/搜索/过滤编排、右键翻译动作（翻译/编辑/重新翻译/删除）、下载管理与三个对话框接线、closeEvent 线程与数据库清理
- **works_list.py** — `WorksListView` + `WorksListModel` + `WorkCardDelegate`：列表虚拟化，仅实例化可见行，卡片全 QPainter 绘制
- **detail_panel.py** — `DetailPanel`（QScrollArea）：完整字段、FlowTags 圆角标签流式布局、可点击厂商、译/原切换、复制
- **workers.py** — `DataWorker` / `ThumbnailWorker`：数据/图片后台线程，信号 queued 回主线程，generation 校验丢弃过期批次
- **top_bar.py / bottom_bar.py** — 顶栏（tab/搜索/排序/状态）与底栏（翻页居中、下载管理/设置入口）
- **download_dialog.py / download_manager_dialog.py / settings_dialog.py** — 下载文件树（三层 tracks 缓存）、任务列表（自绘进度条）、设置五页

## 界面说明

- **顶部导航栏**：列表切换（推荐作品/最新收录/下载作品/没有下载）、刷新按钮、统一搜索框（支持文本输入、标签搜索时替换为彩色标签 chip）、排序下拉框
- **左侧列表区**：显示作品缩略图、标题、彩色标签（点击可搜索）、ID复制按钮和下载状态
- **右侧详情区**：显示选中作品的完整信息，厂商名可点击搜索
- **底部导航栏**：上一页/下一页按钮、页码跳转、设置按钮

## 列表切换

支持四个数据源：
1. **推荐作品**：基于推荐算法的作品列表
2. **最新收录**：按收录时间排序的最新作品
3. **下载作品**：已下载的作品列表（支持排序和分页，切换 tab 自动缓存）
4. **没有下载**：数据库中所有未下载的作品，按发售日期倒序（最新发售在前），由后台自动采集持续补充

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
| `Ctrl+F` | 聚焦搜索框（并全选已有内容） |
| `F5` | 刷新当前列表 |
| `Up` / `Down` | 上一个作品 / 下一个作品（列表区导航，右侧详情同步更新） |
| `Enter` / 双击 | 打开当前选中作品的下载窗口 |

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
- **目录名标题最大长度**：下载文件夹名中标题的最大字符数（默认 120，范围 0-500，填 0 表示不限制）。超出部分自动截断；另受 Windows 路径长度保护（根目录很深时自动收缩，预留子文件夹与文件名空间）
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
- ~~**虚拟滚动**：只渲染可见区域的列表项~~（v2.0.0 已实现：`QListView` + Delegate 全绘制，仅实例化可见行）

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
- ~~**优化滚动性能**：实现虚拟滚动，只渲染可见区域~~（v2.0.0 已实现）
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
1. ~~虚拟滚动优化~~（v2.0.0 已实现）
2. 主题切换功能

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)
