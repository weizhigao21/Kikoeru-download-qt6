## v1.53.0

- **修复**：下载完成主界面底部进度框空边框残留 — `_refresh_task_display` 中无活跃任务时未隐藏 `dl_task_frame` 容器（带 `relief=tk.SOLID, bd=1` 边框），所有下载完成后留一个空白的边框框框。修复后在 `_refresh_task_display` 末尾根据是否有活跃任务 `grid()` / `grid_remove()` 整个容器
- **修复**：作品标题 `♡` 等特殊符号显示乱码 — 列表卡片和详情面板标题标签字体从 `Microsoft YaHei UI` 改为 `Segoe UI`，后者 Unicode 覆盖更广，可正确渲染 ♡、★、♪ 等特殊符号

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
