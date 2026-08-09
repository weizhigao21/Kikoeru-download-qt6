## v2.0.7

代码健康度 / 性能 / 流畅度全面检查后的修复批次：

- **优化：滚轮平滑滚动** — 鼠标滚轮事件原本每格离散大跳（约 3 行 470px）并一次性全量重绘，导致滚动"一卡一卡"（拖动滚动条因连续小步 + 增量平移而流畅）。现 `WorksListView` 拦截 `wheelEvent`：把每格滚动量拆成 16ms 定时器分步滚动（每帧 ≤36px，每格 ≈0.8 行 ≈120px），对齐拖动节奏；连续快速滚动剩余量自动累加衔接，触控板（pixelDelta）走 Qt 原生平滑不受影响，顶部/底部边界由滚动条自动钳制。无头测试 7 项通过（方向/分步/累加/边界/触控板/真实滚动路径）
- **新增：底部实时任务进度条** — 补全 README 声明但缺失的功能：底栏 `dl_task_frame` 由空框架改为增量任务条（`bottom_bar.set_active_tasks`），显示活跃任务的 ID / 进度条 / 百分比 / 速度，任务集合变化时重建、进度变化只改值，无任务自动隐藏；由 `_on_downloads_changed` 每秒刷新
- **修复：两处内存无界增长** — ① `WorkCardDelegate._thumbs` 缩略图字典翻页/搜索从不清理 → `set_works` 时按当前列表裁剪（`prune_thumbs`）；② 直接下载进度字典 `_download_progress` 任务终态从不清理 → 新增 `_cleanup_direct_progress`，在 `_poll_direct_task` 终态 / `_on_task_completed` / `cancel` 中清理，并同步清理 `_slow_restart_count` 残留
- **优化：文件完整性检查并发化** — `_check_files_existence` 逐文件串行 HEAD（timeout 10s×文件数）→ `ThreadPoolExecutor(8)` 并发，保持结果顺序，异常时回退串行；断点续传/重试场景下载启动显著加快
- **优化：缩略图并发加载** — `ThumbnailWorker.load` 单线程串行下载 20 张图 → 4 线程池并发（generation 过期校验保留，新批次取消旧排队任务），翻页首屏缩略图出现更快；新增 `stop()` 供退出时关闭线程池
- **优化：文件夹整理移出轮询线程** — `_flatten_folders`（含失败重试 sleep）原在全局轮询线程同步执行、阻塞其他任务进度轮询 → 改为独立后台线程（`_flatten_worker` + `_flattening` 互斥标志）
- **优化：缩略图重绘合并** — `_on_thumb_ready` 每张图触发一次全量 `viewport().update()` → `QTimer.singleShot(0)` 合并同一帧内的多次就绪（`_flush_thumb_repaint`）
- **优化：下载 tab 列表缓存** — `_load_downloads` 同排序且数据未变化时直接复用 `_all_downloaded_works` 本地展示，不再每次切 tab 全量重查库；删除记录 / 下载完成 / 刷新时显式失效，排序切换同步缓存键
- **修复：退出时线程销毁崩溃风险** — `closeEvent` 中 `QThread.wait(2000)` 超时后线程仍运行即随窗口析构 → 新增 `_stop_worker_thread`：quit + wait(3000)，超时则 detach（`setParent(None)` + `finished`→`deleteLater` + 持有引用），避免 "QThread: Destroyed while thread is still running"
- **修复：APIClient 依赖注入形同虚设** — 注入的 `session`/`cache` 从未生效（方法委托到模块级全局）→ 模块级 fetch 函数增加 `cache`/`session` 可选参数并透传（读取与写入均走注入实例），README 声称的"依赖注入便于测试"现在真实有效
- **修复：版本号不一致** — `config.VERSION` 仍为 v2.0.5（窗口标题/启动画面显示旧版本）→ 同步为 v2.0.7
- **优化：详情面板复用译文缓存** — `show_work(work, is_downloaded, translated=None)` 接收调用方已持有的译文，未传时才回退 DB 查询，避免频繁点击列表项时主线程重复 SQLite 查询
- **清理：tkinter 遗留死代码** — `cache.py` 删除 `get/get_image/save_image/save_thumbnail/get_thumbnail/load_from_url/is_cached/preload_thumbnails/_preload_worker/_resize_thumbnail` 等约 200 行 ImageTk 方法（仅归档版 legacy_tk 使用），并让磁盘超限清理由实际加载路径 `_load_pil_from_url` 触发
- **清理：其他死代码** — 删除 `get_downloader`（downloader.py）、`get_download_progress`/`clear_download_progress`（downloader_direct.py）及 `__init__.py` 相应导出；`src/__init__.py` 移除无人使用的 `API_URL`/`DEFAULT_PAYLOAD` 导出
- **其他低风险修复** — ① `database.py get_work_detail_cached` 消除 `SELECT *`（仅取 vas/circle_data 两列）；② `format_size`/`format_duration` 提取到 `src/utils.py` 统一复用；③ `get_stats` 磁盘大小带 30s TTL 缓存，设置页复用不再全目录遍历；④ Aria2 启动探测 10s → 5s（0.2s 间隔）；⑤ 直接下载 429 重试分支关闭流式 response 防连接泄漏；⑥ `TracksModel.parent()` 线性扫描改行号查表；⑦ `history._parse_tags` 类名静态引用改 `self`；⑧ 删除 4 处未使用导入（pending/database sqlite3、download_dialog SMALL/TITLE_BOLD、works_list QPixmap）

## v2.0.6

- **修复：翻页/搜索后滚动条不回到顶部** — `WorksListModel.set_works` 全量重建 model 后 QListView 会按 index 维持旧滚动位置；新增 `WorksListView.set_works(works, scroll_to_top)` 统一入口（翻页/搜索/刷新传 `True`，延迟一帧 `scrollToTop`），详情刷新 / 隐藏作品 / 删除记录等局部刷新场景传 `False` 保持滚动位置（`main_window.py` 275/487/809/851 行调用点已按场景调整）
- **回滚：作品列表标签换行功能** — 标签显示（含封面尺寸/卡片高度/标签第二行沉底/布局缓存等系列调整）经多次调优仍不达预期，回滚至 v2.0.5 原始状态（封面 180×135、卡片 155、标签单行超宽截断、标题垂直居中），仅保留滚动位置重置改进

## v2.0.5

- **新增：厂商搜索 chip** — 点击详情页厂商名称后，顶栏搜索框区域显示粉色「厂商: xxx」chip（带 ✕ 可移除，颜色对齐 tkinter 版 #E91E63）；点击 ✕ 移除后仍剩标签则继续搜索，无条件则回到进入搜索前的页面（`top_bar.set_circle_chip` / `_on_circle_removed`）
- **新增：厂商 + 标签组合搜索** — 厂商 chip 与标签 chips 可共存并排显示，搜索同时按厂商与标签过滤（API 组合语法 `$circle:xx$ $tag:yy$` 空格分隔，实测紧挨会返回 0 结果；worker 新增 `combo` 类型，`_search_current_conditions` 统一分发）；翻页 / chip 移除 / 历史回退均按组合条件处理
- **修复：标签搜索混入无标签作品** — `_encode_tags` 原将标签作为普通关键词传给后端全文搜索（标题/简介/ID 也匹配），导致名称含关键词但无该标签的作品被搜出；单标签改为 `$tag:xx$` 精确语法（实测 20/20 命中、结果总数 9318<9377），多标签保持空格分隔 AND（后端不支持 `$tag:a$$tag:b$`，会返回 0）
- **新增：下载作品 tab 本地搜索** — 在「下载作品」tab 点击标签 / 厂商或关键词搜索只走本地数据库过滤（`_search_in_downloaded_works`，对齐 tkinter `filter_mixin`，在 `_all_downloaded_works` 上按标签/厂商/关键词组合过滤），不再调用 API 查询接口；切换到「最新/推荐」tab 才走 API 搜索（ID 搜索除外，保持全局查询）
- **新增：切 tab 保留搜索条件** — `_on_tab_changed` 不再调用 `_clear_search_state`，关键词 / 厂商 / 标签与 chips 在切换 tab 时保留，切到新 tab 后用同一条件继续搜索（下载 tab 加载完成后自动本地过滤）
- **修复：组合搜索下标签 chip 无法移除** — `_on_tag_removed` 移除最后一个标签且仍有厂商条件时不刷新 chips，导致标签 chip 残留；改为始终调用 `set_tag_chips`（空列表也清除）
- **修复：普通分页页码输入框不更新** — `_load_data` 未更新 `page_entry`，最新 / 推荐 tab 普通翻页时页码始终显示 1；补充 `setText`

## v2.0.4

- **修复：下载作品的繁简转换不生效**：
  1. **作品文件夹名不转换**：`WorkDownloader._get_save_dir` 生成下载目录名（`{作品ID}-{标题}`）时未做繁简转换，而转换流程（`process_directory`）只处理文件名不处理目录名 → 标题为繁体时整个作品文件夹保持繁体；现改为生成目录名时直接转为简体（受"繁简转换"开关控制）
  2. **重命名竞态**：转换线程在下载完成瞬间启动，文件可能仍被 aria2/Defender 短暂占用导致 `os.rename` 失败即跳过；现改为 `convert_filename` 重命名失败后延迟重试 4 次（0.5s 间隔）

## v2.0.3

- **打包模式：onedir 文件夹 + 外部资源路径回退**（启动提速：单文件 onefile 解压慢 2 秒+，onedir 免解压，实测启动 4-6 秒 → 约 1.4 秒）：
  1. `音声浏览下载.spec` 使用 onedir 模式（`dist/音声浏览下载/`：单个 exe + `_internal/` 依赖目录），分发时整个目录压缩为 zip；保留 `optimize=2`
  2. **外部资源 exe 旁优先、打包内容回退**：`aria2/`（exe 旁 `aria2/` 优先 → `_internal/aria2/` 回退；`config.json` 的 `aria2_dir` 可指定绝对路径）、`settings/`（config.json 与数据库，首次运行自动创建；ui.ico 默认图标打进 `_internal/settings/` 作回退）、`downloads/`（`config.json` 的 `download_dir` 可指定绝对路径）
  3. `src/config.py` 新增 `_get_pkg_root`（`sys._MEIPASS`）与 `_resolve_first`（exe 旁优先）路径回退：`ICON_PATH`、`ARIA2_DIR` 均支持"exe 旁 → 打包内容"两级查找
  4. spec `excludes` 排除 tkinter / pywin32 全家 / pythonnet / pyreadline3 等未用库（拦截 `pywin32_bootstrap` 元路径引导误收集，体积 64.7MB → 58.5MB）

## v2.0.2

- **优化**：打包后启动速度整体提速 — 四项改动：
  1. **模块导入瘦身**：`src/__init__.py` 移除顶层业务模块导入（`get_api_client`/`DatabaseManager`/`get_downloader` 等 5 个），`import src` 不再连带加载 requests/PIL/下载器（实测 0.028s、零重库加载）；各使用方改为从具体子模块导入，`main_window.py` 同步调整
  2. **砍掉 tkinter 加载**：`cache.py` 顶层 `from PIL import Image, ImageTk` 拆为仅 `Image`，`ImageTk`（会连带 `import tkinter`）懒加载到 5 个 tkinter 专属方法内部；`fonts.py` 的 `tkinter.font` 移入 `get_tag_font()` 内懒加载 — Qt6 版启动不再加载 tcl/tk（节省打包体积约 5-10MB + tcl 解释器初始化时间）
  3. **启动画面 + 延迟初始化**：新增 `QSplashScreen` 启动画面（`app.py`，深色底 + 应用名 + 版本，主窗口完全显示后自动关闭）；`MainWindow` 的已下载集合查询 / 未完成任务恢复 / 翻译配置 / 首页数据 4 项非关键初始化延迟到 `QTimer.singleShot(0)` 空闲期执行，主窗口秒出
  4. **打包模式 onefile → onedir**：`音声浏览下载.spec` 改为输出文件夹（`dist/音声浏览下载/`），启动无需解压 PyQt6 全量依赖（onefile 每次启动解压耗时明显），并开启 `optimize=2`；分发时整个目录压缩为 zip 发布

## v2.0.1

- **修复**：下载时每个音频文件单独创建一个文件夹 — Qt 版下载对话框 `TracksModel.node_path`（`download_dialog.py`）把叶子节点自身的文件名也拼进 `subfolder`（如 `track1.mp3/`），提交时 `os.path.join(save_dir, subfolder)` 为每个文件建同名文件夹。改为只拼接 `type=="folder"` 的祖先节点、叶子自身不算路径、根级叶子返回空串（对齐 tkinter 版 `item_folder_path` 的 `current_path` 行为）
- **修复**：下载目录名未使用已翻译标题 — `_open_download_dialog`（`main_window.py`）打开下载对话框时未传 `display_title`（译文），提交时 `submit_work["title"]` 保持原文，`WorkDownloader._get_save_dir` 生成的目录名用原文。补传 `model.translated_title(work) or work["title"]`（对齐 tkinter 版 `list_mixin._get_display_title`），无译文时回退原文
- **变更**：PyInstaller 打包入口切换 — `音声浏览下载.spec` 入口由 `gui_app.py`（tkinter，已归档）改为 `app.py`（Qt6），README 补充打包说明
- **文档**：README 修正 Qt6 迁移后的残留描述（Canvas/Progressbar/控件池/import_downloaded.py 等 tkinter 术语与失效章节）、补充标签 chip 颜色区分描述

## v2.0.0

- **重大变更**：UI 框架从 Tkinter 迁移到 Qt6（PyQt6）— 长列表流畅度、跨线程安全、现代观感的整体换代。业务层（下载管理、数据库、API、翻译/转换服务）零改动复用。tkinter 版已归档至 `legacy_tk/`（git 历史可回退）
- **新增**：列表虚拟化 — `QListView` + `WorksListModel` + `WorkCardDelegate` 全绘制卡片，仅实例化可见行（每页约 10-12 个 widget，原 tkinter 约 340 个），滚动/翻页流畅
- **新增**：跨线程安全 — 数据/缩略图加载改为 `QThread` + `moveToThread`，结果经 signal/slot queued 自动回主线程（替代 `root.after(0, ...)` 手动调度 + `_nav_generation` 防过期）；图片管线后台 `QImage` 解码 → `QByteArray` → 主线程 `QPixmap.fromImage`
- **新增**：详情面板重写 — `QScrollArea` 完整字段展示、`FlowTags` 圆角标签流式布局、可点击厂商搜索、标题译/原切换 + 复制、封面大图、隐藏/刷新/删除下载记录
- **新增**：三个对话框重写 — 下载选择（`QTreeView` + 自定义树模型，三层 tracks 缓存）、下载管理（`QTableView` + 自绘进度条 delegate、正在下载/已完成双页）、设置（左侧导航 + `QStackedWidget` 五页）
- **新增**：列表右键翻译子菜单 — 右键作品弹出「翻译」子菜单，含**翻译标题 / 编辑翻译 / 重新翻译 / 删除翻译**四个动作（编辑用多行输入框、重新翻译清空内存+DB 缓存后强制走 API、删除恢复原文）
- **新增**：翻译缓存列表显示 — 翻页/搜索/过滤后批量读取 `translations` 表注入模型，列表卡片与详情面板直接显示译文（对齐 tkinter 版卡片行为）
- **新增**：翻页控件居中显示；下载窗口文件树列头显示「名称 / 文件大小 / 时间」（`TracksModel.headerData` + `QHeaderView` QSS）
- **新增**：窗口图标使用 `settings/ui.ico`（标题栏 + 任务栏 + 对话框）；标签点击搜索 — 列表卡片与详情面板的标签均可点击按标签搜索（对齐 tkinter 版），支持**多标签累积**（点击不同标签追加条件，顶栏显示多个并排靠左的标签 chip，每个带 ✕ 可单独移除），chip 使用标签色池**循环上色**（多标签颜色区分、悬停加深），点击标签后搜索框/搜索按钮隐藏、移除全部标签后恢复
- **修复**：标签/版本标签点击命中错位 — 卡片绘制（paint）与点击命中（_tag_at/_edition_sid_at）的标题行高计算不一致：paint 用译文标题（`_display_title`），命中用原文标题，有翻译缓存时卡片内容下移 26px，点击标签落空；统一提取 `_title_extra` 使绘制与命中共用同一计算
- **新增**：快捷键 `Ctrl+F`（聚焦搜索并全选）、`F5`（刷新）；列表 Enter/双击统一走 `activated` 信号打开下载窗口（避免双触发）
- **修复**：厂商搜索翻页失效 — 搜索结果回调无条件重置页码把翻页打回第 1 页，移除回调中页码重置
- **修复**：分页数显示错误（显示 1/1 实际 4 页）— API 总数在 `pagination.totalCount` 而非 `total`，`_extract_total()` 兼容新旧格式
- **修复**：右键翻译报「未配置 API Key」但配置存在 — Qt 版启动时未把 config 同步给 translator 单例，补 `_init_translator`
- **修复**：翻译结果未落库 — 保存键 `source_id` 与查询键数字 `id` 不一致，统一为 `str(work["id"])` 落库
- **修复**：`_on_close` 线程/数据库清理迁移到 Qt `closeEvent`（线程 `quit`+`wait` + 四库 `close_all`）
- **入口变更**：默认启动命令 `python app.py`（或 `python -m src.ui.qt.app`），替代 `python src/gui_app.py`

## v1.61.0

- **优化**：翻页渲染性能 — 列表卡片渲染三处热点优化（每页 20 张卡片 × ~17 个 widget）：
  1. **批量翻译查询**：`display_works_list`（`list_mixin.py`）原本每张卡片单独执行 `get_translated_title`（每次新建 SQLite 连接 + SELECT，约 20 次全阻塞在 UI 线程）。新增 `DatabaseManager.get_translated_titles`（`database.py`）一次 `WHERE work_id IN (...)` 批量查询，翻页时 20 次 → 1 次，结果统一传给 `_update_slot`
  2. **editions 标签池化**：`_update_slot`（`list_card.py`）原来每次翻页 `destroy()` 全部 edition Label 再逐个重建，改为 `_edition_labels` 池复用，翻页仅 `config(text/foreground)` 更新 + `pack_forget` 隐藏多余项，不再反复创建销毁 widget
  3. **hover 去递归**：`_hover_children`（`list_card.py`）每次鼠标 Enter/Leave 递归遍历约 340 个子 widget 逐个 `cget`/`config`，连续滚动时频繁触发。改为 hover 仅改卡片 frame 背景，删除递归函数（清理死代码）

## v1.60.2

- **修复**：搜索不存在的 RJ ID 时 `_on_search_success` 崩溃 `AttributeError: 'NoneType' object has no attribute 'get'` — 搜索不存在/API 404 时 `fetch_work_detail`（`api_client.py:187`）返回 `None` 而不抛异常（404 是正常 HTTP 响应，不算请求失败），`_search_by_id_async`（`search_mixin.py:373`）未判空，把 `None` 经 `after(0, _on_search_success, None)` 传给回调，`work_data.get("source_id")` 对 `None` 调用崩溃。修复：`_search_by_id_async` 异步边界加 `not work_data` 检查，`None`/空 dict 路由到 `_on_search_error` 弹出"未找到 RJ{id} 的作品"提示。覆盖普通 ID 搜索（`search_mixin.py:170`）与版本 ID 搜索（`search_mixin.py:368`）两条路径（`_on_search_success` 全项目唯一调用方）

## v1.60.1

- **修复**：下载窗口树刷新竞态导致 `TclError: Item not found` 连环报错 — 点"刷新"或重新加载时 `display_tree` 执行 `tree.delete` 清空整棵树重建，旧 item id（如 I005）全部失效，但 `_prev_selection` 未随之重置。下次 `<<TreeviewSelect>>` 事件触发 `on_select` 时 `newly_deselected` 混入失效 id，`get_children(item_id)` 抛 `TclError`；且异常发生在循环中途，`_prev_selection` 更新行永远执行不到，失效 id 持续残留，导致每次点击都重复报错。修复：①`display_tree`（`gui_download.py:145`）重建前重置 `_prev_selection` 并清空 `download_tasks`/`item_folder_path` 旧映射（避免多次刷新累积旧 id）；②`on_select` 循环加 `self.tree.exists(item_id)` 防御，失效 id 直接跳过，保证 `_prev_selection` 总能正常更新

## v1.60.0

- **新增**：作品文件树(tracks)持久化缓存 — 双击作品弹出的下载窗口文件树原本只有内存缓存（`_APICache` TTL 120 秒），重启或超时后重新打开都要重新请求 API。新建 `WorkTracksManager`（`src/database/tracks.py`）将完整 tracks JSON（含 `mediaDownloadUrl`）持久化到 `download_history.db` 的 `work_tracks` 表。`DownloadWindow.load_tracks`（`gui_download.py:102`）改为三层查询（内存缓存 → DB 缓存 → API 拉取并落库），首次打开后再次双击同一作品秒级加载、无 API 请求。DB 复用 `DOWNLOAD_HISTORY_DB_PATH`，与 `pending_tasks` 共库
- **新增**：下载窗口"刷新"按钮 — 永久缓存策略下的手动刷新机制。点击强制绕过缓存重新请求 API 拉取文件列表并更新 DB 缓存，后台线程执行不阻塞 UI
- **新增**：下载 URL 失效自动回退 — tracks 里的 `mediaDownloadUrl` 可能因 CDN 签名/token 过期失效，原重试机制用原始 URL 反复重试必然失败。`_retry_task`（`manager_poll.py`）首次自动重试前调 `_refresh_task_urls` 重新拉取 tracks，按 `(subfolder, filename)` 映射键替换 `task.files` 的 URL；新增 `DownloadTask.urls_refreshed` 字段保证只刷新一次（无论成败都置 True，避免每次重试都打 API）；刷新失败降级为原重试行为。`_iter_tracks_leaves` 路径构造与 `gui_download.py` 的 `process_node` 一致（含 `unknown` 节点不拼接 title 的特殊处理）
- **修复**：`gui_app.py` `_on_close` 漏关 `pending_task_db` 连接 — `close_all` 是实例级（`BaseDatabaseManager` 每实例独立 `_all_conns` 注册表），原代码只 close 了 `db` 和 `download_history`，`pending_task_db` 的工作线程连接泄漏。补上 `pending_task_db` 及新增 `tracks_db` 的 close_all

## v1.59.3

- **重构**：字体集中管理模块 `src/ui/fonts.py` — UI 层字体声明原本散落在 8 个文件、92 处硬编码元组（如 `("Microsoft YaHei UI", 10)`），每次调整字体需全局搜索替换，易漏改。新建 `fonts.py` 集中定义 3 个字体族常量（`UI_FONT_FAMILY`/`MONO_FONT_FAMILY`/`EMOJI_FONT_FAMILY`）+ 11 个语义化字体元组（`DEFAULT`/`SMALL`/`BODY`/`TITLE_BOLD`/`MONO_ID`/`EMOJI` 等），8 个 UI 文件改为导入常量。今后改字体族只需改 `fonts.py` 一处
- **重构**：`list_card.py` 的 `_TAG_FONT` 全局缓存 + `_get_tag_font()` 迁移至 `fonts.py:get_tag_font()` — Canvas 文本测量需 `tkfont.Font` 对象而非元组，统一由 `fonts.py` 提供并惰性缓存，消除 list_card.py 中 `tkfont` 导入和重复缓存定义
- **统一**：`gui_download_manager.py` 百分比显示字体由 `("Consolas", 9)` 统一为 `MONO_NUM`（`("Consolas", 10)`）— 与 `gui_app_ui.py` 任务栏百分比字体一致，消除历史遗留字号不一致

## v1.59.2

- **回退**：UI 层全部字体由 "Microsoft JhengHei UI" 改回 "Microsoft YaHei UI" — v1.59.0 曾将全局字体统一替换为 JhengHei UI（微米黑），但用户反馈"看着不舒服"。根因：Microsoft JhengHei UI 是繁体中文字体，采用 CNS11643（台湾）字形标准，而项目面向大陆简体用户，应使用 GB 标准字形。"骨""草""过""送" 等字在繁体字形下笔画走势与大陆习惯不同，造成视觉违和。改回 YaHei UI（微软雅黑 UI，Windows 标准 UI 字体，简体 GB 字形）
- **约定**：特殊符号控件（如 📋 复制按钮）维持 Segoe UI Emoji 字体不变 — 共 3 处（detail_mixin.py:62/86、list_card.py:122），不受全局字体回退影响。原 v1.59.0 为修复 ♡ 符号而全局换字体的做法是错误的，正确做法是局部处理符号控件
- **更新**：user_profile.md 与 project_memory.md 字体偏好记录同步修正，标注 JhengHei UI 已废弃及原因，避免下次被再次推翻

## v1.59.1

- **修复**：直接下载模式下重试任务报 `ConnectionRefusedError` — 用户从 Aria2 切换到直接下载后重启，持久化的旧任务恢复时 `download_method` 仍为 "aria2"（[manager.py:224](src/download/manager.py) `restore_pending_tasks` 直接读取持久化旧值，不跟随当前全局 `_config.DOWNLOAD_METHOD`）。重试时 `if task.download_method == "aria2":` 守卫为真，调用 `purge_aria2_downloads` 连接未运行的 Aria2 → `WinError 10061`。改为恢复时用当前全局 `DOWNLOAD_METHOD` 覆盖，并在方式变化时记录 info 日志
- **修复**：`purge_aria2_downloads` / `remove_aria2_downloads` 在 Aria2 未运行时记录完整 traceback — `ConnectionRefusedError`（`OSError` 子类）是预期情况（清理操作时 Aria2 可能已退出或已切换下载模式），不应作为错误记录。新增 `except OSError` 分支静默返回（`logger.debug`），仅非连接类异常才记 `logger.exception`

## v1.59.0

- **修复**：UI 层全部 92 处 "Microsoft YaHei UI" 字体声明统一替换为 "Microsoft JhengHei UI" — 用户明确要求优先使用 "Microsoft JhengHei UI" 以改善中文和特殊符号（如 ♡）在小字号下的可读性。涉及 8 个文件：gui_settings.py（29 处）、list_card.py（16 处）、gui_app_ui.py（13 处）、detail_mixin.py（12 处）、gui_download_manager.py（11 处）、search_mixin.py（6 处）、gui_download.py（3 处）、list_mixin.py（2 处）
- **删除**：tree_selector.py 中 `TreeBuilder` 和 `SelectionManager` 两个死代码类 — 全项目无调用（仅 `__init__.py` 重导出但无人引用），约 235 行冗余代码（含 `__main__` 示例块）。同步更新 `__init__.py` 移除导入，清理仅被这两个类使用的 `tk`/`Optional`/`Any` 导入
- **修复**：tree_selector.py `print_tree_structure` 的 `print` 违反项目硬约束 — 改为 `logger.debug` 并用 `%s` 参数化（v1.57.0 下载层同类修复的延续）
- **修复**：tree_selector.py `notify_selection_changed` 静默吞异常 — `except Exception: pass` 改为 `logger.debug("选择回调执行异常", exc_info=True)`，保留调试信息
- **修复**：gui_settings.py `save_settings` 残留 `os.fsync(f.fileno())` — v1.44.0 changelog 声称已移除但实际仍存在，强制物理磁盘写入导致配置保存缓慢。删除该调用（`with` 块关闭时已自动 flush）
- **修复**：gui_settings.py `logger.exception` 冗余异常参数 — `logger.exception("复制 %s 失败: %s", db_name, e)` 中 `e` 参数多余，`logger.exception` 已自动附加异常 traceback。改为 `logger.exception("复制 %s 失败", db_name)`
- **重构**：gui_download_manager.py 状态映射重复消除 — `_build_active_row` 和 `_update_progress` 两处重复的状态文本+颜色映射逻辑提取为 `_STATUS_MAP` 常量和 `_get_status_text_color` 方法
- **重构**：gui_download_manager.py 字符串状态比较改为 `TaskStatus` 枚举比较 — 与 v1.55.0 gui_app_ui.py 的重构一致
- **重构**：list_card.py `_DEFAULT_COLORS` 常量提取 — `_create_slot` 和 `_update_slot` 两处重复的 11 行颜色字典提取为模块级常量
- **优化**：list_card.py 3 处 logger f-string 改为 `%s` 参数化 — 与 v1.58.0 translator.py 优化一致
- **修复**：list_card.py 翻译超时计时器未取消 — `_translate_title` 创建的 `after` 计时器在 UI 元素销毁时未取消，可能导致回调访问已销毁控件。添加 `_translation_timeout_timer` 跟踪并在销毁时 `after_cancel`
- **删除**：gui_download.py 冗余 `_normalize_rj_id` wrapper — v1.55.0 已抽取 `normalize_rj_id` 到 utils.py 并改为薄包装调用，wrapper 本身无存在意义。删除 wrapper，直接调用 `normalize_rj_id`

## v1.58.0

- **修复**：`_translator` 全局单例无锁保护 — `get_translator()` 的 `if _translator is None: _translator = TranslatorService()` 非线程安全。多线程同时首次调用（如启动时多个 list_card 并发翻译）会创建多个实例，最后一个胜出，前几个的缓存丢失。添加 `_translator_lock`，双重检查锁定
- **修复**：`update_config` 首次调用前属性未初始化 — `__init__` 未设置 `_api_key`/`_base_url`/`_model`/`_thinking_enabled`。若 `update_config` 未被调用就执行 `translate`，`_translate_thread` 第 90 行 `self._base_url` 会 `AttributeError`。虽 `gui_app.py` 启动时必调 `_init_translator`，但防御性不足。`__init__` 初始化为空字符串/默认值
- **修复**：`_session` 重建丢失配置 — 第 154-158 行 `RequestException` 时重建 session，但只恢复了 `Content-Type` 和 `Authorization`，若 `update_config` 设置了其他自定义头会丢失。且重建在锁外，多线程可能覆盖。改为用 `self._session.close()` + 重建，在锁内执行，保留 headers
- **优化**：`translator.py` 15 处 logger 用 f-string 改为 `%s` 参数化 — `logger.error(f"...")` 即使日志级别被过滤也会执行字符串格式化。最佳实践是 `logger.error("...: %s", e)` 延迟格式化
- **重构**：`_translate_thread` callback 调用重复 7 次提取 `_safe_callback` — 每个 except 分支都有 `try: callback(None) except Exception as cb_err: logger.error(...)`，约 4 行重复 7 次 = 28 行重复。提取 `_safe_callback(callback, result)` 公共方法
- **修复**：`_vtt_timestamp_to_lrc` 进位 bug — `centiseconds = round(millis / 10)` 可能等于 100（如 `millis=999` → 100），原代码 `seconds += (centis % 100) // 100` 错误地始终返回 0，导致秒数不进位。`00:01.999` 错误输出 `[00:01.00]` 而非正确的 `[00:02.00]`。修正为 `seconds += centis // 100; centis = centis % 100`
- **修复**：`subtitle_converter.py` NOTE 块结束判断不健壮 — 原逻辑：NOTE 块内的行若以制表符或两个空格开头则跳过，否则结束 NOTE 块。但实际 VTT 的 NOTE 块以空行结束，不是靠缩进判断。当前逻辑会把 NOTE 块后的第一行错误地当作 NOTE 内容跳过。改为空行结束 NOTE 块（符合 VTT 规范）
- **优化**：`text_converter.py` 10 处 logger 用 f-string 改为 `%s` 参数化 — 同 translator.py 优化
- **修复**：`convert_file_content` 无编码回退 — 第 23 行 `open(file_path, 'r', encoding='utf-8')`，若文件是 Shift-JIS 编码会 `UnicodeDecodeError`。`subtitle_converter.py` 已处理此情况但 `text_converter` 未同步。增加回退编码：UTF-8 失败后尝试 Shift-JIS
- **优化**：`convert_filename` 重命名失败语义不清 — 第 63 行 `return file_path`（失败）和第 64 行 `return file_path`（无需转换）语义相同，调用方无法区分是否失败。添加注释说明返回值语义，日志带 `[繁简]` 前缀
- **优化**：`translate` 流程可读性差 — 空文本 callback 后 return，缓存命中后也 return，逻辑正确但可读性差。添加注释说明三个分支（空文本/缓存命中/启动线程）

## v1.57.0

- **修复**：下载层 41 处 `print` 严重违反项目硬约束 — `downloader.py` 18 处、`downloader_direct.py` 8 处、`manager.py` 5 处、`manager_core.py` 10 处。v1.48.0 changelog 声称已全部替换为 `logging`，但下载层是重灾区，PyInstaller 打包后 `print` 刷屏且无级别控制。全部替换为 `logger`（info/warning/exception），与 `manager_poll.py` 已有的正确用法一致
- **重构**：删除 `_get_aria2_proxy` thread-local 代理，统一用 `_get_global_aria2_proxy` — `WorkDownloader._get_aria2_proxy()` 用 `threading.local` 缓存每线程 ServerProxy，`_get_global_aria2_proxy()` 用全局单例。XML-RPC ServerProxy 本身是线程安全的，无需 thread-local 缓存。`download_file`/`download_file_async` 改用全局代理，消除两种获取方式并存的混乱
- **修复**：`submit` 重复提交防护缺少 CONVERTING 状态 — 第 80 行检查 `SUBMITTING/DOWNLOADING/QUEUED` 时返回，但 `CONVERTING` 状态未包含。字幕转换期间重复提交会覆盖正在转换的任务。添加 `TaskStatus.CONVERTING` 到检查条件
- **重构**：`_submit_aria2`/`_submit_direct` 文件存在性检查重复消除 — v1.50.0 changelog 声称已提取 `_check_files_existence` 公共方法，但实际仍是内联重复（约 30 行 × 2）。提取 `_check_files_existence(files, save_dir)` 返回 `(files_to_download, skipped_count)`，两个方法调用
- **重构**：空文件完成处理重复消除 — v1.50.0 changelog 声称已提取 `_handle_task_completion`，但实际未做。`_submit_aria2`/`_submit_direct` 的 `if not files_to_download:` 块完全相同（约 10 行），提取为 `_handle_task_completion(task)`
- **重构**：三个 persist 方法结构相同提取 `_safe_persist` — `_persist_task`/`_remove_persisted`/`_sync_task_status` 都是 `if self._pending_db is None: return` + `try: self._pending_db.xxx() except Exception as e: print(...)`。提取 `_safe_persist(action, error_msg, *args)` 公共方法
- **重构**：`_retry_task`/`_auto_restart_slow_task` 清理逻辑重复消除 — 两者都有"等待旧线程 → 清理 aria2/direct → 重置 task 字段"结构，仅等待超时不同（30s vs 120s）。提取 `_cleanup_and_reset_task(task, thread_join_timeout)` 公共方法
- **修复**：`downloader.py` `shell=True` 残留 — v1.48.0 changelog 声称已移除 `shell=True`，但 `subprocess.Popen([aria2_exe], ..., shell=True)` 实际仍在。列表参数 + `shell=True` 语义混乱，移除 `shell=True`
- **删除**：`_download_cover_image`/`_save_tags_file` 无意义 wrapper — 两个方法仅调用 `self.save_cover_image(save_dir)` 和 `self.save_tags(save_dir)`，增加一层无意义间接。删除 wrapper，直接调用
- **重构**：`save_cover_image` 的 numeric_id 解析用 `strip_rj_prefix` — 第 108 行 `source_id.replace("RJ","").replace("rg","").replace("RG","").lstrip("0")` 与 v1.55.0 抽取的 `strip_rj_prefix` 功能重叠。替换为 `strip_rj_prefix(source_id).lstrip("0")`
- **清理**：`ensure_aria2_running` 循环变量 `i` 未使用 — `for i in range(20)` 中 `i` 从未使用，改为 `for _ in range(20)`
- **修复**：`get_remote_file_size` HEAD 失败无回退 — 某些 CDN 对 HEAD 请求返回 405，导致返回 -1 误判文件不完整重新下载。HEAD 失败（405/异常）时回退到 GET stream + 只读 content-length，不下载内容
- **重构**：429 限流处理重复消除且同步 Retry-After 头 — `download_file` 中两处 `wait_time = retry_wait * (2 ** attempt) + 5` + `print` + `time.sleep` 完全相同，且未读取 `Retry-After` 头（v1.55.0 已在 api_client.py 修复但此处未同步）。提取 `_handle_429(response, attempt, max_retries)` 公共方法，优先读 `Retry-After` 头（上限 60s），回退到指数退避

## v1.56.0

- **重构**：数据库层提取 `BaseDatabaseManager` 基类 — `DatabaseManager`/`DownloadHistoryManager`/`PendingTaskManager` 三个类的 `_connect` contextmanager 完全相同（35 行 × 3 = 105 行重复）：threading.local 连接缓存、300 秒超时重连、WAL + synchronous=NORMAL、try/except rollback+close。新增 `src/database/base.py` 基类包含 `_connect`/`close_all`/`_safe_json_load` 公共方法，三个管理器改为继承，消除最严重的 DRY 违规
- **修复**：`close_all` 只关闭当前线程连接导致其他线程连接泄漏 — `_local.conn` 是 thread-local 的，`close_all` 只关闭调用者线程的连接。gui_app.py 的 `_on_close` 在主线程调用，但工作线程（轮询/下载/预加载）的连接不会被关闭。基类新增全局连接注册表 `_all_conns`，`_register_conn`/`_unregister_conn` 在 `_connect` 中维护，`close_all` 遍历关闭所有线程连接
- **删除**：三个数据库类的 `self._lock` 死代码 — `__init__` 都创建 `self._lock = threading.Lock()`，但 `_connect` 和 `close_all` 都只操作 `_local`（thread-local 无需锁）。`_lock` 从未被使用，直接删除
- **重构**：`_safe_json_load` 默认值逻辑简化 — 原实现 `return default if default is not None else ([] if default == [] else {})` 用 `==` 比较 default 与空列表，写法绕且 `default=None` 时返回 `{}` 不直观。简化为 `return default if default is not None else {}`（default 非 None 时直接返回，已覆盖 [] 和 {}）
- **修复**：`get_work_detail_cached` 直接用 `json.loads` 而非 `_safe_json_load` — database.py 第 188-189 行 `json.loads(vas_str)` 若 vas_str 是损坏 JSON 会抛异常，未用同类已有的 `_safe_json_load` 保护。改为 `self._safe_json_load(vas_str, [])` 和 `self._safe_json_load(circle_str, {})`，与同类其他方法一致
- **修复**：`history.py` `add_download` 的 `print` 违反项目硬约束 — 第 135 行 `print(f"添加下载历史失败: {e}")` 应改用 `logger`。改为 `logger.exception("添加下载历史失败")`
- **修复**：`add_download` 的 `except Exception` 吞掉异常后仍提交 — try 块内 `cursor.execute` 失败后进入 except 打印，但 `conn.commit()` 在 try 块内，失败时不执行。移除 try/except，让异常传播给 `_connect` 的 contextmanager 自动 rollback，调用方能感知失败
- **修复**：`history.py` tags 用逗号分隔不安全 — `add_download` 第 122 行 `",".join(tags)` 存储，`get_all_downloaded_works_full` 第 176 行 `split(",")` 解析，若标签名含逗号会被错误分割。tags 改用 `json.dumps` 序列化，新增 `_parse_tags` 兼容旧逗号格式（优先尝试 JSON，回退到 split）
- **修复**：`pending.py` `get_all_pending` 缩进 bug 导致只返回第一条 — 原 `return result` 在 `for` 循环内，循环执行一次就 return，导致 `get_all_pending` 永远只返回最新的一条任务。`return result` 移到循环外，正确返回所有持久化任务
- **重构**：`cache.py` 提取 `_process_image` 公共方法 — `save_image` 和 `save_thumbnail` 的 RGBA→RGB 转换、mode 检查、JPEG 保存逻辑完全相同（约 30 行），仅 cache_key 和是否缩略不同。提取 `_process_image(img_data)` 返回处理后的 PIL.Image，两个方法复用
- **修复**：`cache.py` 两处 `print` 违反项目硬约束 — 第 192 行 `print(f"保存图片失败: {e}")` 和第 222 行 `print(f"保存缩略图失败: {e}")` 改为 `logger.exception(...)`
- **修复**：`_schedule_disk_cleanup` 锁释放逻辑 bug — `acquire(blocking=False)` 成功后启动线程，但 `except` 块释放锁，而 `_cleanup_disk_cache` 在 `finally` 中也会 `release()`。`Thread.__init__` 几乎不会抛异常，`except` 块是死代码且逻辑混乱。移除 try/except，直接启动线程（`_cleanup_disk_cache` 的 finally 保证锁释放）
- **清理**：`get_stats` 方法内重复 `import os` — cache.py 第 285 行 `import os` 在方法内重复导入，但文件第 1 行已导入。删除方法内的冗余导入
- **优化**：预加载队列有序化 — `_preload_queue` 原为 `set`，`pop()` 无序弹出，预加载顺序不可控可能先加载远处的图片。改为有序 `list` + 去重 `set`，`preload_thumbnails` 按距离 `current_index` 排序后追加，`_preload_worker` 从头部 `pop(0)`，优先加载当前附近的缩略图
- **修复**：`clear_memory_cache` 直接操作 LRUCache 内部属性绕过锁保护 — `self.memory_cache.cache.clear()` 直接访问 LRUCache 的内部 OrderedDict，若其他线程同时 `get`/`put` 可能不一致。LRUCache 新增 `clear()` 加锁方法，`clear_memory_cache` 改为调用 `self.memory_cache.clear()`

## v1.55.0

- **修复**：主窗口关闭时资源泄漏 — `WorkApp` 未注册 `WM_DELETE_WINDOW` 关闭协议，关闭窗口后 `_thumb_pool`/`_data_pool` 两个 `ThreadPoolExecutor` 从不 `shutdown`，数据库连接也不释放，进程可能挂起。新增 `_on_close` 方法：注册关闭协议、`shutdown(wait=False)` 两个线程池、调用 `close_all()` 关闭 `db`/`download_history`，最后 `root.destroy()`
- **重构**：`_normalize_rj_id` 三处重复实现合并 — `gui_app.py`、`history.py`、`gui_download.py` 中完全相同的字符串处理逻辑（`replace("RJ","").replace("rg","").replace("RG","").strip().zfill(6)`）抽取为 `src/utils.py` 的 `normalize_rj_id` 公共函数，三处改为薄包装调用。消除 DRY 违规，后续只需维护一处
- **修复**：`gui_app.py` 多处 `print` 输出违反项目硬约束 — 图标加载失败、启动恢复异常、加载已下载 ID 失败三处 `print` 全部改用 `logger.warning`/`logger.exception`，并带 `exc_info` 保留堆栈
- **修复**：`logging.basicConfig(level=logging.DEBUG)` 写在模块顶层导入区 — 生产环境 DEBUG 级别会产生海量日志，且若其他模块先导入 logging 此调用会失效。移入 `if __name__ == "__main__":` 块，级别改为 `INFO`
- **修复**：启动时序耦合脆弱 — `after(100, self._on_startup_restore)` 与 `after(150, self.load_data_async)` 硬编码时序，恢复持久化任务未完成时网络加载已启动。改为 `_on_startup_restore` 在 `finally` 中回调启动 `load_data_async`，确保恢复完成后再加载数据
- **修复**：图标加载异常过宽 — `except Exception` 收窄为 `except (OSError, ValueError)`，避免吞掉 `KeyboardInterrupt`/`SystemExit` 等不应捕获的异常
- **修复**：设置窗口可重复打开导致引用泄漏 — `open_settings` 未做去重，连续点击"设置"会创建多个 `SettingsWindow`，旧窗口引用丢失但未关闭。复用 `open_download_manager` 的 `winfo_exists` 检查模式，已存在则 `lift`+`focus_force`；注册 `WM_DELETE_WINDOW` 清理 `_settings_win` 引用；`_settings_win` 初始化为 `None` 避免 `AttributeError`
- **重构**：`TaskStatus` 枚举比较替换字符串硬编码 — `gui_app_ui.py` 中 `t.status.value in ("submitting","downloading",...)` 等 4 处字符串比较改为 `t.status in (TaskStatus.SUBMITTING, ...)` 枚举值比较，与 `manager.py`/`manager_poll.py` 等模块一致，避免拼写错误且利于重构
- **修复**：字幕转换阶段底部进度框误隐藏 — `_refresh_task_display` 的活跃任务过滤未包含 `TaskStatus.CONVERTING`，与 `manager_poll.py:44` 的过滤条件不一致，导致字幕转换期间底部进度框被误判为无活跃任务而隐藏。新增 `CONVERTING` 到过滤条件，并增加"转换中"状态文本显示
- **修复**：缓存失效标记线程不安全 — `_on_dl_tasks_changed` 中 `self._downloaded_cache_valid = False` 是普通赋值，而同方法内 UI 更新已通过 `after(0)` 调度到主线程。缓存失效标记改为同样用 `root.after(0, lambda: setattr(...))` 调度，保持一致的线程安全策略
- **重构**：`setup_ui` 拆分为 4 个私有方法 — 原 `setup_ui` 约 130 行同时构建顶部/左侧/右侧/底部 4 个区域 + 详情面板，违反单一职责。拆分为 `_build_top_bar`/`_build_list_area`/`_build_detail_area`/`_build_bottom_bar`，`setup_ui` 只做编排
- **清理**：`_create_task_slot` 初始化循环简化 — `for i in range(1)` 只执行一次却用循环语法包裹，造成可扩展误导。改为直接调用一次 `_create_task_slot()`
- **删除**：`switch_tab` 死代码 — `NavigationMixin.switch_tab` 是空 `pass` 实现，全项目无调用，v1.44.0 changelog 声称提取导航公共方法但此方法从未实现或使用。直接删除
- **修复**：`gui_app_nav.py` 魔法数字未替换为常量 — v1.44.0 changelog 声称已将 `show_downloaded` 魔法数字替换为 `SHOW_ALL`/`HIDE_DOWNLOADED`/`DOWNLOADED_TAB` 常量，但本文件 8 处仍是数字 `1/2/3`，与 `filter_mixin.py`、`search_mixin.py` 等其他文件不一致。导入常量替换全部 8 处
- **修复**：异常日志级别过低 — `_fetch_from_api`/`_fetch_latest_from_api` 的 `except Exception` 分支用 `logger.debug` 记录错误，DEBUG 级别在生产环境（INFO）下不会输出，导致加载失败问题难以诊断。改为 `logger.exception` 保留完整堆栈
- **重构**：翻页搜索分支代码重复消除 — `go_to_page`/`prev_page`/`next_page` 中"厂商搜索"和"关键词搜索"分支代码（`_bump_generation`+`show_loading`+新建线程调用 `_search_by_circle_async`/`_search_by_keyword_async`）约 12 行重复 3 次。提取 `_navigate_search(page)` 公共方法，三处统一调用
- **优化**：无数据时取消弹窗 — `_on_data_loaded` 在作品列表为空时弹 `messagebox.showinfo("提示", "当前页没有数据")`，异步加载回调中弹模态对话框阻塞主线程，且翻到空页频繁弹窗影响体验。改为 `status_label.config(text="当前页没有数据")` 状态栏提示
- **修复**：切换到下载作品 tab 时 loading 状态未设置 — `_on_tab_changed` 中切换到"下载作品"tab 且有搜索条件时调用 `_search_in_downloaded_works()` 但未设置 `self.loading = True`，与其他加载路径不一致，期间用户可重复触发操作。新增 `loading = True`
- **修复**：`load_data_async` 闭包竞态 — 内嵌 `load()` 闭包在新线程中直接读写 `self.current_tab`/`self.current_page` 等实例属性，可能被主线程同时修改（如用户快速切换 tab）。虽有 `_nav_generation` 机制保护最终提交，但中间状态读取无保护。改为闭包开始时捕获 `tab_snapshot`/`page_snapshot` 快照变量，闭包内只用快照
- **删除**：`_on_escape` 死代码且会崩溃 — 从未被绑定到 `<Escape>` 快捷键，且方法体内引用 `search_chips`/`title_label`/`btn_row`/`search_button` 4 个全项目无赋值的属性 + `clear_all_items`/`refresh_works` 2 个全项目无定义的方法，若被调用会立即 `AttributeError` 崩溃。直接删除
- **删除**：5 个 `_shortcut_*` 死代码方法 — `_shortcut_prev`/`_shortcut_next`/`_shortcut_download`/`_shortcut_select_prev`/`_shortcut_select_next` 从未被绑定到任何快捷键，`_bind_shortcuts` 只绑了鼠标滚轮和窗口 resize。约 35 行死代码直接删除
- **删除**：`_on_root_resize` 与 list_mixin.py 重复定义 — `EventMixin._on_root_resize` 与 `ListMixin._on_root_resize` 完全相同（都调用 `_schedule_canvas_configure()`），MRO 中 `ListMixin` 在前覆盖 `EventMixin` 版本，`EventMixin` 版本永远不会被调用。删除 `EventMixin` 版本，绑定由 `ListMixin` 接管
- **重构**：`_restore_search_state` keyword/circle 分支代码重复消除 — 两个分支约 12 行结构几乎完全相同（清空其他查询条件 → 设置 page → 更新显示 → `loading=True` → `show_loading` → 新建线程调用 async 方法），仅方法名和状态文本不同。提取 `_restore_async_search(search_type, status_text, update_display, async_method)` 公共方法
- **优化**：`search_history` 列表添加长度上限 — `_push_search_history` 虽截断当前索引之后的历史，但用户持续做新搜索（不回退）时列表会无限增长。新增 `_MAX_SEARCH_HISTORY = 50` 类常量，超限时删除最旧条目并调整索引
- **修复**：`_InFlight.dedup` 并发去重竞态 — 用 `if 'evt' in dir()` 检测局部变量是否已赋值，写法极其非惯用且脆弱：`dir()` 返回当前作用域名称列表，语义本应是"evt 是否已赋值"；第 62-63 行在 `with self._lock` 块内检查 `key in self._inflight` 并取出 `evt`，但第 64 行 `if 'evt' in dir()` 在锁外执行——若两个线程同时进入，线程 A 创建 evt 后线程 B 的 `evt` 可能未赋值就到了第 64 行检查，`dir()` 不含 `evt` 导致 B 误走"新建 fetcher"分支，破坏去重语义。重构为局部变量 `existing` 接收 evt，锁外用 `if existing is not None` 判断；首个调用者执行 fetcher，等待者复用结果/异常
- **修复**：`_fetch_or_dedup` 失败时重复请求 — 流程：① 先查缓存（miss）→ ② `_inflight.dedup` 调 fetcher（fetcher 内部 `_cache.put`）→ ③ `_cache.get` 取结果。但 `dedup` 用 `try/except: pass` 吞掉 fetcher 异常（第 89-90 行），若 fetcher 抛异常，`_cache.get` 返回 `None`，第 93 行又调一次 `fetcher()`——同一个失败请求被调用两次，且第二次调用结果不缓存也不去重，完全绕过保护。移除 `try/except: pass` 吞异常，让异常透传给所有等待者；移除 fallback 二次调用 fetcher
- **重构**：`fetch_works_page`/`fetch_latest_works_page` 函数体完全相同 — 两者 URL、params、响应解析逻辑一字不差，仅 cache_key 前缀不同（`"works"` vs `"latest"`），约 25 行重复代码。提取 `_fetch_works_page_impl(key_prefix, page, page_size)` 公共实现，两函数改为薄包装
- **重构**：`search_by_tag`/`search_by_keyword`/`search_by_circle` 响应解析逻辑完全相同 — 三者的 `if data is None ... elif isinstance(data, dict) and "works" in data ...` 链完全一致，约 25 行重复 3 次。提取 `_parse_search_response(data, page, page_size)` 解析函数 + `_search_impl(key, encoded_query, page, page_size)` 请求实现，三个函数改为薄包装（消除约 75 行重复）
- **重构**：`fetch_work_detail`/`fetch_tracks` RJ ID 规范化重复 — 两处 `if str(rid).startswith("RJ"): rid = str(rid)[2:]; rid = str(int(rid))` 完全相同，且与 `src/utils.py` 的 `normalize_rj_id` 功能重叠（v1.55.0 已抽取）。但 `normalize_rj_id` 返回零填充字符串，这里需要纯数字。新增 `strip_rj_prefix(rj_id)` 到 `utils.py` 返回纯数字字符串，两处调用替换内联逻辑
- **优化**：429 限流响应读取 `Retry-After` 头 — 硬编码 `RETRY_DELAY * (2 ** attempt)` 指数退避，但 HTTP 429 标准的 `Retry-After` 头可能指定精确等待时间。忽略它可能等待过短（立即再被限流）或过长（不必要延迟）。改为优先读取 `Retry-After` 头解析为秒数（上限 60s），回退到指数退避
- **优化**：`APIClient` 支持依赖注入 — 模块级 `_session`/`_cache`/`_inflight` 全局单例在模块加载时创建，测试时无法替换 mock。`APIClient.__init__` 新增可选 `session`/`cache` 参数，默认使用模块级单例，便于未来测试
- **修复**：`config.py` `VERSION` 未同步 — CHANGELOG 和 README 已升到 v1.55.0，但 `config.py` 的 `VERSION` 仍是 `"v1.54.0"`。`gui_app.py` 用它设置窗口标题 `f"音声浏览下载 {VERSION}"`，用户看到的版本号错误。改为 `"v1.55.0"`
- **删除**：`_friendly_error` 死代码 — 定义在 config.py 第 111 行，全项目无调用。这是一个 UI 辅助函数（将技术错误转为友好提示），放在 config.py 中职责不清且从未被使用。直接删除（16 行）
- **修复**：`SUBTITLE_CONVERT_ENABLED` 默认值矛盾 — `_DEFAULT_CONFIG` 第 35 行设为 `False`，但第 106 行 `_cfg.get("subtitle_convert_enabled", True)` 的 fallback 是 `True`。虽然第 66-68 行的合并逻辑确保 key 一定在 `_cfg` 中（值为 False），fallback 永不触发，但这是混淆点。改为 `_cfg["subtitle_convert_enabled"]` 直接索引
- **修复**：配置文件解析错误静默吞掉 — `except Exception:` 静默回退到空字典，配置文件损坏（JSON 语法错误）或权限不足时用户不知道配置丢失，所有自定义设置突然消失。拆分为 `except FileNotFoundError:`（首次运行，静默）+ `except Exception as e:`（记录 `warning` 日志）
- **重构**：16 处冗余 `.get(key, default)` 统一为 `_cfg[key]` 直接索引 — 第 66-68 行合并逻辑已确保所有 `_DEFAULT_CONFIG` 的 key 都在 `_cfg` 中且非 None，所以第 91-108 行的 `.get(key, default)` fallback 永远不会触发。而第 70-73 行的 `API_URL`/`ARIA2_RPC_URL` 等用 `_cfg[key]` 直接索引。风格不一致，全部统一为直接索引

## v1.54.0

- **修复**：下载任务进行中时打开新作品下载窗口卡顿约 20 秒 — `fetch_tracks` 是唯一未走缓存/去重路径的 API 函数，每次打开下载窗口都重新请求网络；当已有下载任务占满带宽时，请求超时（15s）+ 重试退避累计约 20s。改为走 `_fetch_or_dedup`，与 `fetch_work_detail` 等其他 API 函数一致，重复打开同一作品秒开（120s LRU 缓存 + 并发去重）
- **修复**：下载管理窗口 observer 跨线程操作 tkinter 导致 UI 卡顿 — `DownloadManagerWindow._refresh` 作为 observer 在轮询线程被直接调用并操作 widget，违反 tkinter 线程安全，与主线程竞争 Tcl 解释器锁。新增 `_schedule_refresh` 方法，用 `window.after(0, ...)` 将刷新调度到主线程执行（与主窗口 `_on_dl_tasks_changed` 一致）
- **新增**：`load_tracks` 增加 `fetch_tracks` 耗时日志，便于定位下载窗口文件列表加载延迟

## v1.53.0

- **修复**：下载完成主界面底部进度框空边框残留 — `_refresh_task_display` 中无活跃任务时未隐藏 `dl_task_frame` 容器（带 `relief=tk.SOLID, bd=1` 边框），所有下载完成后留一个空白的边框框框。修复后在 `_refresh_task_display` 末尾根据是否有活跃任务 `grid()` / `grid_remove()` 整个容器
- **修复**：作品标题 `♡` 等特殊符号显示乱码 — 列表卡片和详情面板标题标签字体从 `Microsoft YaHei UI` 改为 `Microsoft JhengHei UI`，Unicode 覆盖更广，可正确渲染 ♡、★、♪ 等特殊符号，且小字号阅读更舒适

## v1.52.0

- **新增**：AI 翻译思考模式（DeepSeek） — 设置 → AI 翻译新增"启用思考模式"开关（默认开启）。开启后请求添加 `thinking: {"type": "enabled"}` + `reasoning_effort: "high"` 参数，翻译更准确但响应更慢；思考模式下自动省略不支持的温度参数（`temperature`）并将 `max_tokens` 提升至 1024；翻译请求超时自动放宽至 90 秒、UI 超时保护放宽至 100 秒
- **优化**：AI 翻译设置页滚动 — 设置窗口 AI 翻译页内容较多时超出窗口高度，改为 Canvas + Scrollbar 可滚动区域，鼠标滚轮可直接滚动
- **修复**：下载完成判断过早导致文件移位和繁简转换不执行 — `_submit_direct` 中 task_id 边下载边注册（文件间 2 秒间隙），`poll_direct_progress` 在间隙中误判 `all_resolved=True` 提前标记 COMPLETED。改为下载前预生成所有 task_id 注册到 `task.direct_task_ids`，未开始的 task_id 在 `_download_progress` 中无条目 → poll 计为 `unresolved`，确保所有文件完成后才触发整理和转换
- **修复**：`poll_direct_progress` 修改共享 `task_ids` 集合并行冲突 — 移除 `task_ids.discard()` 调用，改用只读快照迭代
- **修复**：进度条左右跳动（11%→50%→4%） — `_poll_direct_task` 中 `completed_bytes` 改为 `max(task.completed_bytes, completed)` 历史最大值，配合 `peak_total_bytes` 实现进度只增不减
- **修复**：`_auto_restart_slow_task` 不等待旧下载线程导致 `KeyError` 崩溃 — 新增 `thread.join(timeout=120)` 等待旧线程退出后再清理 `_download_progress`
- **修复**：`download_file` 中 `_download_progress` 访问非防护崩溃 — 新增 `_set_progress()` 安全 helper，KeyError 时静默跳过代替崩溃；10 处不安全直接访问全部替换
- **修复**：重试/重启场景残留进度数据 — `_retry_task` 和 `_auto_restart_slow_task` 重新提交前清理 `_download_progress` 旧记录，防止 poll 看到旧 "error" 状态立即触发无限重试循环

## v1.51.0

- **新增**：VTT→LRC 字幕转换实现 — `subtitle_converter.py` 桩代码替换为完整实现：解析 VTT 时间戳（HH:MM:SS.mmm → [mm:ss.xx]）、跳过 WEBVTT 头部/NOTE/STYLE 块、移除 HTML 标签（`<c>` `<i>` `<b>` 等）、支持 UTF-8（含 BOM）和 Shift-JIS 编码、转换后自动删除原 `.vtt` 文件
- **修复**：字幕转换文件名后缀残留 — 转换后 `.mp3.vtt` → `.mp3.lrc` 问题修复，新增 `_strip_audio_suffix_and_vtt` 函数自动识别并去除 10 种常见音频后缀（.mp3/.wav/.flac/.m4a/.ogg/.wma/.aac/.opus/.ape/.wv），`track01.mp3.vtt` 正确转为 `track01.lrc`
- **修复**：自动整理文件夹与字幕转换间歇性失效 — `_poll_loop` 退出时与 `_ensure_polling` 存在竞态条件：轮询循环准备退出时新任务提交被忽略，导致后续任务无人监控、整理和转换永不执行。轮询循环改为永不退出，空闲时 30 秒深度睡眠，新任务通过 `_poll_wake_event` 唤醒；`_ensure_polling` 不再简单地返回，而是主动唤醒已有轮询线程
- **修复**：字幕转换完成后自动整理延迟过长 — `_convert_subtitles_and_complete` 和 `_on_task_completed` 现在主动 `set()` 唤醒事件，轮询循环立即检测到任务完毕并执行自动整理，无需等待下次轮询周期
- **修复**：`_do_pending_flatten` 中途失败丢失后续目录 — 从一次性 `clear()` 全部列表改为 `pop(0)` 逐个处理，失败只影响当前目录

## v1.50.0

- **新增**：繁简转换功能 — 下载完成后自动将繁体字幕内容和文件名转换为简体中文，使用 `zhconv` 库实现；设置 → 下载设置中新增"启用繁简转换"开关，位于"自动整理文件夹"下方
- **修复**：翻译按钮卡在"翻译中" — 翻译 API 超时或异常时按钮状态无法恢复。`translator.py` 增加 30 秒超时保护和全面异常捕获确保回调始终执行；`list_card.py` 增加 35 秒 UI 超时计时器，超时后自动恢复按钮状态
- **重构**：文件检查逻辑重复消除 — `_submit_aria2` 和 `_submit_direct` 中约 50 行重复的文件存在性检查逻辑提取为 `_check_files_existence` 公共方法，任务完成处理提取为 `_handle_task_completion` 公共方法，降低维护成本 50%

## v1.49.0

- **新增**：自动整理文件夹开关 — 文件选择窗口新增"自动整理文件夹"复选框，可临时关闭本次下载的文件夹整理；设置 → 下载设置中新增默认开关，持久化到 config.json
- **修复**：取消勾选自动整理后仍会整理 — `_on_task_completed` 中 `except Exception` 分支在配置检查异常时仍会添加到待整理列表，移除 try/except 包裹

## v1.48.0

- **修复**：下载任务卡在"提交中" — `print→logger` 重构时意外破坏 `_submit_aria2` 和 `_submit_direct` 逻辑（添加了错误的 `return files_to_download` 提前返回 + `ThreadPoolExecutor` 改写），导致后续提交代码全部变成死代码。恢复原始顺序循环检查文件完整性 + `if not files_to_download: → COMPLETED` 处理
- **修复**：重复下载 — `_download_progress` 全局字典跨下载尝试累积残留数据（旧 task_id 的 "complete" 状态），导致 `poll_direct_progress` 误判 `all_resolved=True` 提前标记完成。新增 `_submit_direct` 开始前清理旧进度条目、`submit()` 检查旧任务下载线程是否存活、`_retry_task` 等待旧线程结束后再启动新线程
- **修复**：文件夹提前整理 — `_poll_loop` 在任务标记完成后立即调用 `_do_pending_flatten()`，但 `download_sequential` 线程可能还在运行。新增 `task.download_threads` 跟踪下载线程、`_poll_direct_task` 检查线程存活后才标记 COMPLETED、`_poll_loop` 检查线程存活后才执行整理
- **修复**：进度条跳动（显示100%后回落到80%） — `poll_direct_progress` 只计算已注册的 task_id，当一个文件完成、下一个文件还没注册时 `total` 变小导致进度回退。新增 `_peak_total_bytes` 历史最大值防止 `total` 下降，未全部完成时进度上限 99.9%
- **修复**：`filter_mixin.py` 缺少 `import tkinter as tk` — 第 366 行使用 `tk.NORMAL` 但未导入，隔离环境下会崩溃
- **修复**：`downloader.py` 使用 `shell=True` — `subprocess.Popen` 配合列表参数时语义混乱，移除 `shell=True`
- **修复**：`downloader.py` 无效 `global` 声明 — 函数级 `global` 变量未在模块级别定义
- **重构**：`print()` 全部替换为 `logging` — 78 处 `print()` 改为 `logger` 调用，14 个文件添加 `logger = logging.getLogger(__name__)`，消除 PyInstaller 打包后 `print` 刷屏问题
- **清理**：未使用导入和变量 — `gui_app.py` 清理 7 个未使用导入，`api_client.py` 移除未使用异常变量，`manager_core.py` 移除 `ThreadPoolExecutor/as_completed`，其他文件清理未使用导入
- **新增**：`build.bat` 一键打包脚本 — 自动清理 build/dist 目录、调用 PyInstaller、验证输出文件

## v1.47.0

- **修复**：直接下载模式文件夹提前整理 — `_submit_direct` 中 task ID 采用懒创建（下载线程启动时才生成），导致 `poll_direct_progress` 的 `list(task_ids)` 快照可能遗漏尚未创建的 ID，误判 `all_resolved=True` 提前触发文件夹扁平化。改为预先创建所有 task ID，确保 poll 时能看到完整任务列表

## v1.46.0

- **修复**：文件夹整理不全 — 修复 `_poll_loop` 启动时重置 `_pending_flatten` 导致已完成任务的目录丢失，以及所有文件跳过时 `_ensure_polling` 未调用导致整理永不执行的问题
- **优化**：文件夹整理重试 — `_flatten_folders` 对移动失败的文件自动重试 3 次（间隔 2 秒），解决 Windows 文件锁导致的整理失败

## v1.45.0

- **新增**：已下载作品多语言关联标记 — 列表卡片和详情面板中其他语言版本标签显示下载状态（绿色 ✓ 表示已下载）
- **新增**：批量扫描关联功能 — 已下载 Tab 新增"扫描关联"按钮，批量获取已下载作品的多语言版本信息并标记

## v1.44.0

- **修复**：翻译出错时程序崩溃 — `list_card.py` 缺少 `logger` 定义，翻译失败时抛出 `NameError`
- **修复**：已下载作品排序无效 — `_load_downloaded_works` 忽略 `sort_key` 参数，始终按下载时间排序
- **优化**：作品详情加载性能 — `_lookup_cached_detail` 改为按 ID 单条查询，不再全量加载所有已下载作品
- **优化**：补全信息性能 — `_fetch_missing_thumbnails` 用字典查找替代 O(n) 遍历，大量作品时显著提速
- **优化**：程序关闭速度 — 移除配置文件写入中的 `os.fsync` 调用
- **重构**：`show_downloaded` 魔法数字替换为 `SHOW_ALL`/`HIDE_DOWNLOADED`/`DOWNLOADED_TAB` 常量
- **重构**：导航方法提取 `_load_current_page()` 公共方法，消除 `go_to_page`/`prev_page`/`next_page` 中的重复代码
- **重构**：硬编码颜色值统一到 `COLORS` 字典，新增 `tag_chip`/`keyword_chip`/`circle_chip`/`detail_bg`

## v1.43.0

- **优化**：文件夹整理延迟执行 — `_flatten_folders` 改为所有下载任务完成后批量执行，不再在单个任务完成时立即执行，防止下载过程中干扰其他任务
- **优化**：EXE 图标修复 — 禁用 UPX 压缩，确保 Windows 文件管理器正确显示程序图标
- **优化**：下载标题截取 — 标题截取从按字符数（50字符）改为按显示宽度（150宽度），中文标题不再截断丢失字符
- **修复**：直接下载进度解包错误 — `poll_direct_progress` 返回值从 4 个增加到 5 个，修复 `ValueError` 崩溃
- **修复**：Aria2 多文件下载进度计算 — 完成文件的大小现在计入总进度，避免跳动现象
- **修复**：直接下载无 content-length 时卡死 — 无 content-length 的任务现在能正确标记完成，不再超时
- **修复**：文件夹整理崩溃 — `shutil.move` 改为 `os.replace` 并添加异常捕获，轮询线程不会因为单个文件失败而中断
- **优化**：项目结构调整 — 主程序入口文件迁移到 src 目录，spec 文件和 README 文档相应更新
- **优化**：底部下载进度框动态显隐 — 底部下载任务进度框仅在有活跃下载任务时显示，无任务时自动隐藏

## v1.35.0

- **修复**：「隐藏下载」翻页过滤失效 — 启用「隐藏下载」后翻页时新页数据未重新应用过滤器，修复 `_on_data_loaded` 和搜索成功回调共 4 条路径

## v1.27.0

- **修复**：下载作品重复加载 API 补全信息 — `update_work_detail` 方法 RJ ID 格式不匹配，修复为使用规范化后的 ID
- **修复**：下载作品缓存频繁失效 — `_on_dl_tasks_changed` 改为仅在任务完成或失败时使缓存失效
- **修复**：作品信息完整性误判 — 空声优数组和空厂商字典视为"已获取"，避免重复请求 API
- **优化**：作品缓存初始化 — `_load_downloaded_works` 加载后立即初始化 `_fetched_ids`，减少不必要的 API 请求

## v1.14.0

- **优化**：全局下载管理器 — `DownloadManager` 单例统一管理所有下载任务，支持多作品并行下载
- **优化**：下载窗口解耦 — 去掉轮询/回调/转移逻辑，窗口仅负责文件选择和提交
- **优化**：底部任务列表 — 从单一进度条改为多行任务列表，固定槽位 + grid 布局消除闪烁
- **修复**：多标签搜索 — `_encode_tags` 分隔符从 `$` 改为空格，多标签搜索不再返回 0 结果
- **优化**：数据库路径自定义 — `config.json` 新增 `db_dir` 配置项，设置窗口支持浏览和迁移
- **优化**：UI 更新优化 — 任务列表更新时复用控件只改数值，不再销毁重建

## v1.13.1

- **修复**：翻页到第3页程序卡死 — `LRUCache` 改为非阻塞锁获取，绝不阻塞主线程
- **修复**：`_on_tab_changed` loading 状态永久锁定 — 拦截时将 `tab_var` 恢复为当前 tab
- **修复**：`show_loading()`/`hide_loading()` 控件安全性 — 销毁前检查 `winfo_exists()`
- **修复**：`_InFlight.dedup()` 竞态条件 — 使用 `evt.wait()` 等待 + `_results` 缓存结果

## v1.13.0

- **优化**：添加数据库索引 — `works.work_id`、`works.page`、`download_history.rj_id`、`download_history.created_at`
- **优化**：添加 API 请求缓存 — LRU 缓存，最多 100 条，TTL 120 秒
- **优化**：Session 连接复用 — API 请求使用 `requests.Session` 复用 TCP 连接
- **优化**：图片压缩保存 — 保存时自动压缩为 JPEG 85% 质量
- **优化**：磁盘缓存清理 — 超 500MB 自动删除最旧文件
- **优化**：数据库连接池 — `threading.local()` 缓存每线程连接
- **优化**：请求合并 — API 请求增加进行中请求去重（`_InFlight`）
- **优化**：批量更新 — 移除 `update_idletasks()` 强制刷新，进度更新改用共享可变状态节流

## v1.12.1

- **修复**：线程安全问题 — `ImageTk.PhotoImage` 改为主线程创建，`StringVar.get()` 改为主线程读取后传参
- **修复**：标签换行计算不准确 — `_draw_tags_on_canvas` 改为基于 Canvas 实际宽度自适应换行

## v1.12.0

- **修复**：下载进度查询竞态条件 — 改为先收集待删除 GID 再统一删除
- **修复**：数据库连接泄漏 — 全部方法改用 `contextmanager` 确保连接关闭
- **修复**：内存泄漏风险 — 图片缓存添加磁盘空间管理（默认 500MB 上限）
- **修复**：`is_downloaded()` 性能问题 — 从全表加载改为 SQL 直接查询
- **修复**：裸 `except:` 语句 — 全部改为 `except Exception:`
- **修复**：`ImageCacheManager` 缺失方法 — 恢复被误删的 `get()`、`get_http_session()` 等方法
- **修复**：详情页图片尺寸错误 — 详情页正确加载 400×400 高清封面（mainCoverUrl）
- **修复**：mainCoverUrl 未持久化 — 懒加载获取的高清封面 URL 写入数据库
- **修复**：声优/厂商重复请求 — 懒加载前先查询本地数据库，命中则跳过 API
- **优化**：设置窗口缓存管理 — 新增缓存大小显示和"清除缓存"按钮
