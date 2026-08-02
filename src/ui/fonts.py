"""UI 字体集中管理模块。

所有字体声明统一从此模块导入，改字体只改本文件。
- UI_FONT_FAMILY: 主 UI 字体族（简体中文）
- MONO_FONT_FAMILY: 等宽字体族（ID/百分比/速度等数字显示）
- EMOJI_FONT_FAMILY: emoji 字体族（特殊符号控件，如 📋）
"""
import tkinter.font as tkfont

# 字体族常量 —— 改字体族只改这里
UI_FONT_FAMILY = "Microsoft YaHei UI"
MONO_FONT_FAMILY = "Consolas"
EMOJI_FONT_FAMILY = "Segoe UI Emoji"

# UI 字体元组（按语义命名，size+weight 组合）
DEFAULT = (UI_FONT_FAMILY, 10)               # 默认 UI 字体
DEFAULT_BOLD = (UI_FONT_FAMILY, 10, "bold")  # 默认粗体
SMALL = (UI_FONT_FAMILY, 9)                  # 小字号
TINY = (UI_FONT_FAMILY, 8)                    # 极小字号（按钮/速度/版本信息）
BODY = (UI_FONT_FAMILY, 11)                   # 正文（导航/搜索框/详情标题）
LABEL = (UI_FONT_FAMILY, 11, "bold")          # 详情页字段标签（标题:/封面:等）
TITLE = (UI_FONT_FAMILY, 14)                  # 下载窗口标题
TITLE_BOLD = (UI_FONT_FAMILY, 14, "bold")     # 模块大标题（设置页/详情页）

# 等宽字体（数字显示）
MONO_ID = (MONO_FONT_FAMILY, 9, "bold")       # 作品 ID 显示
MONO_NUM = (MONO_FONT_FAMILY, 10)             # 百分比/页码等数字

# Emoji 字体（特殊符号控件，独立于全局 UI 字体）
EMOJI = (EMOJI_FONT_FAMILY, 10)               # 📋 复制按钮

# Canvas 专用 Font 对象缓存
# Canvas 文本测量（measurebbox）需要 tkfont.Font 对象而非元组，惰性创建并缓存
_tag_font_cache = None


def get_tag_font():
    """获取标签字体 Font 对象（Canvas 文本测量用，惰性创建并缓存）。

    从 list_card.py 迁移至此，统一管理。
    """
    global _tag_font_cache
    if _tag_font_cache is None:
        _tag_font_cache = tkfont.Font(family=UI_FONT_FAMILY, size=9)
    return _tag_font_cache
