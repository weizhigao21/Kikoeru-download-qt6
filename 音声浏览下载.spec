# -*- mode: python ; coding: utf-8 -*-

# onedir 模式（v2.0.3+）：打包输出为文件夹 dist/音声浏览下载/（含单个 exe + _internal/ 依赖目录），
# 启动无需解压，显著提升启动速度（单文件 onefile 每次启动需解压约 58MB，实测慢 2 秒+）。
# 分发时可将整个 dist/音声浏览下载/ 目录压缩为 zip 发布。
#
# 外部资源（exe 旁优先，打包内容回退，见 src/config.py）：
#   - aria2/（aria2.exe 等）：不再打包进 exe（v2.1.0 起），需在 exe 旁放 aria2/ 目录；config.json 的 aria2_dir 可指定绝对路径
#   - settings/（config.json / 数据库）：exe 旁自动创建；ui.ico 默认图标打进 _internal/settings/ 作回退
#   - downloads/（下载目录）：默认 exe 旁 downloads/，config.json 的 download_dir 可指定绝对路径

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('settings/ui.ico', 'settings'), # 默认图标，找不到 exe 旁图标时回退使用
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',               # Qt6 版不再使用 tkinter，避免误打包 tcl/tk（约 10MB）
        'pywin32_bootstrap',     # pywin32 元路径引导：阻断 win32 全家（win32com/Pythonwin/约10MB）收集
        'pywin32', 'pythonwin', 'win32com', 'pyreadline3',  # 未使用
        'pythonnet',             # .NET 互操作，未使用
        'numpy',                 # 项目不用 numpy，排除 OpenBLAS（约 47MB，被 Pillow/其他 hook 误收集）
        'PyQt6.QtPdf',           # 不用 PDF 渲染（约 4.4MB）
        'PyQt6.QtPdfWidgets',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir：二进制与数据由下方 COLLECT 收集
    name='音声浏览下载',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='settings\\ui.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='音声浏览下载',
)
