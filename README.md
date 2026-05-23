# 音声作品浏览下载

一个基于 Tkinter 的桌面应用程序，用于浏览和下载 ASMR 音声作品。

## 版本

**v1.27.0**（当前版本）

## 功能特性

### 浏览与搜索
- **三列表浏览**：支持"推荐作品"、"最新收录"和"下载作品"三个数据源切换
- **分页浏览**：支持按页查看作品列表，每页显示 20 个作品
- **标签搜索**：点击任意标签快速筛选同类作品，支持多标签组合搜索（AND 交集），每个标签可单独移除
- **关键词搜索**：统一搜索框，自动识别输入为 RJ ID 或关键词进行模糊搜索
- **厂商搜索**：点击详情页厂商名称搜索该厂商的所有作品
- **ID 搜索**：支持通过 RJ ID 精确查找作品
- **多语言版本**：支持点击其他语言版本 ID 快速切换显示
- **搜索框标签芯片**：标签/关键词/厂商搜索时搜索框内显示独立芯片，每个带 ✕ 按钮可单独关闭

### AI 翻译
- **AI 标题翻译**：支持使用 OpenAI 兼容 API（如 DeepSeek、GPT 等）翻译作品标题
- **翻译按钮**：列表中复制按钮旁显示"翻译"按钮，一键翻译当前作品标题
- **标题切换**：翻译完成后标题旁显示"原/译"切换按钮，随时在原文和译文之间切换
- **翻译持久化**：翻译结果保存到数据库，重启后仍然生效
- **下载使用译文**：当标题显示为译文时，下载目录名自动使用译文标题
- **详情页翻译**：详情页自动显示翻译标题，支持"原/译"切换
- **API 可配置**：设置窗口支持配置 API Key、API 地址、模型名称

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
- **下载作品列表**：下拉框"下载作品"tab 直接浏览所有已下载作品，支持排序和分页，切换 tab 时自动缓存避免重复查询
- **懒下载标记**：点击下载即标记已下载状态，无需等待任务提交完成

### 性能优化
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
- **智能翻页按钮**：第一页/最后一页时自动隐藏对应翻页按钮，减少视觉干扰

## 项目结构

- **新增**：`src/ui/detail_mixin.py` - 详情面板（循环滚动、懒加载、CV/厂商显示）
- **新增**：`src/ui/list_mixin.py` - 作品列表（缩略图加载、加载动画、滚动支持、AI翻译）
- **新增**：`src/ui/search_mixin.py` - 统一搜索（ID/标签/关键词、搜索框标签芯片）
- **新增**：`src/ui/filter_mixin.py` - 筛选排序（只看已下载、内存排序、封面补全）
- **新增**：`src/download/manager.py` - 全局下载管理器（单例、统一轮询、观察者模式）
- **新增**：`src/services/translator.py` - AI 翻译服务（OpenAI 兼容 API、翻译缓存）
- 通过 Mixin 多继承组合到 WorkApp，MRO：`WorkApp > DetailMixin > ListMixin > SearchMixin > FilterMixin`

```
g:\code\音声下载\
├── src/                        # 核心业务模块包
│   ├── __init__.py             # 统一导出
│   ├── config.py               # 配置读取（带默认值容错）
│   ├── api_client.py           # API 请求客户端（带指数退避重试 + 缓存去重）
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite 数据库（作品缓存、下载历史、翻译结果独立表）
│   │   └── cache.py            # 图片缓存（LRU内存+磁盘两级缓存）
│   ├── download/
│   │   ├── __init__.py
│   │   ├── downloader.py       # Aria2 下载管理（异步下载、连接复用、进度查询）
│   │   ├── downloader_direct.py # 直接下载模块（HTTP 下载，不依赖 Aria2）
│   │   └── manager.py          # 全局下载管理器（单例、统一轮询、观察者模式）
│   ├── services/
│   │   ├── __init__.py
│   │   └── translator.py       # AI 翻译服务（OpenAI 兼容 API、翻译缓存）
│   └── ui/
│       ├── __init__.py
│       ├── detail_mixin.py     # 详情面板（滚动、懒加载、CV/厂商）
│       ├── list_mixin.py       # 作品列表（缩略图、动画、滚动、AI翻译）
│       ├── search_mixin.py     # 搜索逻辑（ID/标签/关键词/厂商、搜索框芯片）
│       ├── filter_mixin.py     # 筛选排序（已下载、内存排序、封面补全）
│       ├── gui_download.py     # 下载窗口（树形选择、提交即返回、译文标题）
│       ├── gui_settings.py     # 设置窗口（含缓存管理、数据库路径自定义、AI翻译设置）
│       └── tree_selector.py    # 树状图选择工具类
├── gui_app.py                  # 主程序入口（Mixin模式组合）
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
python gui_app.py
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

### src/database/database.py
数据库管理模块，所有操作使用 `contextmanager` 确保连接安全关闭：
- 创建和管理 SQLite 数据库
- 保存和读取作品数据（含声优、厂商、封面、mainCoverUrl）
- 翻译结果独立存储（`translations` 表，按 work_id 索引）
- 管理分页数据
- 下载历史管理（支持增量更新，不重置时间戳）
- RJ ID 统一格式（自动规范化比较）
- `get_work_detail_cached(rj_id)` - 从本地数据库查询声优/厂商信息，命中则跳过 API
- `update_works_cache(work, page)` - 更新作品缓存（含懒加载获取的声优/厂商/封面）
- 数据库索引：`works.work_id`、`works.page`、`download_history.rj_id`、`download_history.created_at`、`translations.work_id`

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

### src/download/manager.py
全局下载管理器（线程安全单例），核心调度层：
- `DownloadManager` — 单例，统一管理所有下载任务的注册、提交、轮询、取消
- `DownloadTask` — 任务数据模型（work_id、gids、进度、状态、速度）
- `TaskStatus` — 任务状态枚举（submitting / downloading / completed / failed / cancelled）
- **提交即返回**：`submit(work, files)` 立即创建任务，后台线程逐一调用 Aria2 addUri
- **Housekeeper**：后台线程静默执行封面下载、标签保存、下载历史写入
- **统一轮询**：有任务时自动启动轮询线程，全部完成后自动退出
- **观察者模式**：`add_observer(callback)` 通知主界面实时更新底部任务列表
- **幂等保护**：同一作品正在下载中再次提交自动忽略

### src/ui/tree_selector.py
树状图选择工具类，提供：
- `select_all()` - 全选所有节点
- `deselect_all()` - 取消所有选中
- `select_all_in_folder(folder_id)` - 全选文件夹内所有内容
- `get_selected_leaf_items()` - 获取选中的叶子节点（文件）
- `invert_selection()` - 反选所有节点
- `expand_all()` / `collapse_all()` - 展开/折叠所有节点

### WorkApp (gui_app.py)
主应用程序类，通过 Mixin 多继承组合功能模块：

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
- **数据库目录**：自定义数据库文件（works.db / download_history.db）存储位置，留空使用默认 `settings/` 目录。路径变更时自动复制旧数据库文件到新位置，提示重启后生效。翻译结果存储在 works.db 的 `translations` 表中
- **图片缓存**：显示当前缓存大小，点击"清除缓存"一键清理（同时清除内存缓存和磁盘缓存文件）
- **AI 翻译设置**：
  - **启用 AI 翻译**：勾选后开启翻译功能，列表中显示翻译按钮
  - **API Key**：填写 OpenAI 兼容 API 的密钥（如 DeepSeek、GPT 等）
  - **API 地址**：填写 API 基础地址（如 `https://api.deepseek.com/v1`）
  - **模型名称**：填写使用的模型（如 `deepseek-chat`、`gpt-3.5-turbo`）

## 已知问题与改进计划

### 🐛 已知Bug

#### 已修复（v1.12.0）
1. ✅ **下载进度查询竞态条件** — 改为先收集待删除 GID 再统一删除
2. ✅ **数据库连接泄漏** — 全部方法改用 `contextmanager` 确保连接关闭
3. ✅ **内存泄漏风险** — 图片缓存添加磁盘空间管理（默认 500MB 上限）
4. ✅ **`is_downloaded()` 性能问题** — 从全表加载改为 SQL 直接查询
5. ✅ **裸 `except:` 语句** — 全部改为 `except Exception:`
6. ✅ **`ImageCacheManager` 缺失方法** — 恢复 `get()`、`get_http_session()` 等被误删的方法
7. ✅ **详情页图片尺寸错误** — 详情页现在正确加载 400×400 高清封面（mainCoverUrl），不再显示 180×180 缩略图
8. ✅ **mainCoverUrl 未持久化** — 懒加载获取的高清封面 URL 现在写入数据库，切换时不再重复请求
9. ✅ **声优/厂商重复请求** — 懒加载前先查询本地数据库（works.db + download_history.db），命中则跳过 API
10. ✅ **设置窗口缺少缓存管理** — 新增缓存大小显示和"清除缓存"按钮

#### 已修复（v1.12.1）
1. ✅ **线程安全问题** — `ImageTk.PhotoImage` 改为主线程创建（新增 `_load_pil_from_url` 方法），`StringVar.get()` 改为主线程读取后传参
2. ✅ **标签换行计算不准确** — `_draw_tags_on_canvas` 改为基于 Canvas 实际宽度自适应换行，不再使用固定数量

#### 已修复（v1.13.1）
1. ✅ **翻页到第3页程序卡死** — `LRUCache.put()` 使用阻塞锁获取（`with self.lock`），后台 8 个 ThreadPoolExecutor 线程频繁竞争锁时，主线程被永久阻塞。修复：`LRUCache` 的 `get()`、`put()`、`remove()` 全部改为非阻塞锁获取（`acquire(blocking=False)`），获取不到锁时跳过缓存操作，绝不阻塞主线程
2. ✅ **`_on_tab_changed` loading 状态永久锁定** — loading 状态下切换 tab 被拦截 return 后，`self.loading` 永远不会被重置，导致所有后续翻页静默失效。修复：拦截时将 `tab_var` 恢复为当前 tab
3. ✅ **`show_loading()`/`hide_loading()` 控件安全性** — 快速翻页时 loading 控件被销毁后仍被访问，引发 TclError。修复：销毁前调用 `winfo_exists()` 检查 + `Progressbar.stop()` 停止内部定时器
4. ✅ **`_InFlight.dedup()` 竞态条件** — 两个线程同时调用 `dedup()` 时，第二个线程没有等待第一个线程完成，导致同一个 API 被请求两次，两个回调先后执行造成界面状态混乱。修复：使用 `evt.wait()` 等待 + `_results` 缓存结果

#### 已修复（v1.27.0）
1. ✅ **下载作品重复加载 API 补全信息** — `update_work_detail` 方法更新数据库时 RJ ID 格式不匹配（带 RJ 前缀更新纯数字 ID），导致声优/厂商信息永远写不进去。修复为使用规范化后的 ID 进行 WHERE 条件匹配
2. ✅ **下载作品缓存频繁失效** — `_on_dl_tasks_changed` 改为仅在下任务完成或失败时使缓存失效，进度更新不再触发缓存失效，避免频繁重新加载
3. ✅ **作品信息完整性误判** — 空声优数组 `[]` 和空厂商字典 `{}` 视为"已获取"而非"缺失"，避免对本身无此信息的作品重复请求 API
4. ✅ **作品缓存初始化优化** — `_load_downloaded_works` 在加载后立即根据数据库中的完整信息初始化 `_fetched_ids`，减少不必要的 API 请求

#### 待修复
暂无

### ⚡ 性能优化建议

#### 已完成（v1.14.0）
- ✅ **全局下载管理器**：`DownloadManager` 单例统一管理所有下载任务，支持多作品并行下载
- ✅ **下载窗口解耦**：去掉轮询/回调/转移逻辑，窗口仅负责文件选择和提交
- ✅ **底部任务列表**：从单一进度条改为多行任务列表，固定槽位 + grid 布局消除闪烁
- ✅ **多标签搜索修复**：`_encode_tags` 分隔符从 `$` 改为空格，多标签搜索不再返回 0 结果
- ✅ **数据库路径自定义**：`config.json` 新增 `db_dir` 配置项，设置窗口支持浏览和迁移
- ✅ **UI 更新优化**：任务列表更新时复用控件只改数值，不再销毁重建

#### 已完成（v1.13.0）
- ✅ **添加索引优化**：`works.work_id`、`works.page`、`download_history.rj_id`、`download_history.created_at`
- ✅ **添加 API 请求缓存**：LRU 缓存，最多 100 条，TTL 120 秒
- ✅ **Session 连接复用**：API 请求使用 `requests.Session` 复用 TCP 连接
- ✅ **图片压缩保存**：保存时自动压缩为 JPEG 85% 质量
- ✅ **磁盘缓存清理**：超 500MB 自动删除最旧文件
- ✅ **数据库连接池**：`threading.local()` 缓存每线程连接，避免频繁创建/销毁
- ✅ **请求合并**：API 请求增加进行中请求去重（`_InFlight`），避免重复请求
- ✅ **批量更新**：移除 `update_idletasks()` 强制刷新、进度更新改用共享可变状态节流

#### 待优化
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

4. **快捷键支持**（v1.12.0 已部分实现）
   - ~~`Ctrl+F`：聚焦搜索框~~
   - ~~`←/→`：翻页~~
   - `Enter`：确认搜索
   - ~~`Esc`：取消当前操作~~
   - `Ctrl+D`：下载选中作品

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

### 📋 优先级建议

#### ✅ 已完成（v1.13.0）
1. ~~修复下载进度查询的竞态条件~~
2. ~~解决数据库连接泄漏问题~~
3. ~~添加内存/磁盘缓存上限~~
4. ~~添加数据库索引~~
5. ~~添加 API 请求缓存~~
6. ~~添加快捷键支持~~
7. ~~详情页高清封面加载（mainCoverUrl 400×400）~~
8. ~~声优/厂商数据库缓存查询（跳过重复 API 请求）~~
9. ~~设置窗口缓存管理（显示大小 + 一键清除）~~
10. ~~线程安全 UI 更新（PhotoImage 主线程创建 + StringVar 主线程读取传参）~~
11. ~~标签换行自适应（基于 Canvas 实际宽度换行）~~
12. ~~数据库连接池（threading.local 缓存连接）~~
13. ~~请求合并（进行中请求去重）~~
14. ~~批量更新（移除非必要 update_idletasks + 进度节流）~~

#### 待实现
1. 虚拟滚动优化
2. 主题切换功能

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)
