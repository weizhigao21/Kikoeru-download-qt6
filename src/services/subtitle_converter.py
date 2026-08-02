"""字幕转换模块 — VTT 转 LRC"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# VTT 时间戳格式: HH:MM:SS.mmm 或 MM:SS.mmm
_VTT_TIME_RE = re.compile(
    r'^(?:(\d{2,}):)?(\d{2}):(\d{2})[\.\,](\d{3})'
)

# WEBVTT 头部 / 样式 / 注释块标记
_WEBVTT_HEADER_RE = re.compile(r'^WEBVTT', re.IGNORECASE)
_NOTE_BLOCK_RE = re.compile(r'^NOTE\b', re.IGNORECASE)
_STYLE_BLOCK_RE = re.compile(r'^STYLE\b', re.IGNORECASE)
_REGION_BLOCK_RE = re.compile(r'^REGION\b', re.IGNORECASE)


def _vtt_timestamp_to_lrc(timestamp_str: str) -> str:
    """将 VTT 时间戳 (HH:)MM:SS.mmm 转为 LRC 时间戳 [mm:ss.xx]"""
    m = _VTT_TIME_RE.match(timestamp_str.strip())
    if not m:
        return None
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    millis = int(m.group(4))

    total_minutes = hours * 60 + minutes
    # 修正进位逻辑：round(millis/10) 可能等于 100（如 millis=999 → 100）
    # 原代码 (centis % 100) // 100 错误地始终返回 0，导致秒数不进位
    centiseconds = round(millis / 10)
    if centiseconds >= 100:
        seconds += centiseconds // 100  # centis=100 → seconds+1
        centiseconds = centiseconds % 100  # centis=100 → 0
    if seconds >= 60:
        total_minutes += seconds // 60
        seconds = seconds % 60

    return f"[{total_minutes:02d}:{seconds:02d}.{centiseconds:02d}]"


def _strip_html_tags(text: str) -> str:
    """移除 VTT 文本中简单的类 HTML 标签，如 <c> <i> <b> <v> 等"""
    return re.sub(r'<[^>]+>', '', text)


def convert_vtt_to_lrc(vtt_content: str) -> str:
    """将 VTT 格式字符串转换为 LRC 格式字符串

    VTT 格式示例:
        WEBVTT

        00:01.000 --> 00:04.000
        - 第一行字幕

        00:05.000 --> 00:09.000
        - 第二行字幕
        - 第二行第二句

    转换后的 LRC 格式:
        [00:01.00]- 第一行字幕
        [00:05.00]- 第二行字幕
        [00:05.00]- 第二行第二句
    """
    lines = vtt_content.split('\n')
    lrc_lines = []
    in_note_block = False
    current_timestamp = None

    for line_raw in lines:
        line = line_raw.strip()

        # 空行：结束 NOTE 块（VTT 规范：NOTE 块持续到下一个空行）
        if not line:
            in_note_block = False
            continue
        if _WEBVTT_HEADER_RE.match(line):
            continue
        if _NOTE_BLOCK_RE.match(line):
            in_note_block = True
            continue
        if _STYLE_BLOCK_RE.match(line) or _REGION_BLOCK_RE.match(line):
            continue

        # NOTE 块内的行全部跳过（直到空行结束）
        if in_note_block:
            continue

        # 检查是否是时间戳行: "00:01.000 --> 00:04.000"
        if '-->' in line:
            parts = line.split('-->')
            if len(parts) >= 2:
                lrc_ts = _vtt_timestamp_to_lrc(parts[0])
                if lrc_ts:
                    current_timestamp = lrc_ts
            continue

        # 跳过 VTT 区块头部（数字行标记了 cue 顺序，如 "1"）
        if re.match(r'^\d+$', line):
            continue

        # 文本行 —— 使用当前时间戳生成 LRC 条目
        if current_timestamp:
            # 移除前导破折号后面多余的空格
            cleaned = _strip_html_tags(line)
            # 保留像 "- 文本" 这样的格式，只去掉前导空白
            lrc_lines.append(f"{current_timestamp}{cleaned}")

    return '\n'.join(lrc_lines)


# 常见音频格式后缀
_AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma', '.aac', '.opus', '.ape', '.wv'}


def _strip_audio_suffix_and_vtt(filename: str) -> str:
    """移除文件名中的音频后缀和 .vtt，替换为 .lrc

    track01.mp3.vtt → track01.lrc
    track01.wav.vtt → track01.lrc
    track01.vtt      → track01.lrc
    """
    base = filename.lower()
    # 必须是以 .vtt 结尾
    if not base.endswith('.vtt') or len(base) <= 4:
        return filename[:-4] + '.lrc'

    # 去掉最后的 .vtt 后的剩余部分
    without_vtt = filename[:-4]
    # 检查是否以已知音频后缀结尾
    base_without_vtt = without_vtt.lower()
    for ext in _AUDIO_EXTS:
        if base_without_vtt.endswith(ext) and len(without_vtt) > len(ext):
            return without_vtt[:-len(ext)] + '.lrc'

    return without_vtt + '.lrc'


def process_subtitle_in_directory(directory: str) -> list:
    """扫描目录下的 .vtt 文件，转换为 .lrc 并删除原 .vtt

    Returns:
        list[str]: 已转换的 .lrc 文件路径列表
    """
    if not os.path.isdir(directory):
        return []

    converted = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if not filename.lower().endswith('.vtt'):
                continue

            vtt_path = os.path.join(root, filename)
            # 输出文件名: 移除音频后缀和 .vtt，替换为 .lrc
            # 例如 track01.mp3.vtt → track01.lrc / track01.vtt → track01.lrc
            lrc_filename = _strip_audio_suffix_and_vtt(filename)
            lrc_path = os.path.join(root, lrc_filename)

            try:
                with open(vtt_path, 'r', encoding='utf-8-sig') as f:
                    vtt_content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(vtt_path, 'r', encoding='shift-jis') as f:
                        vtt_content = f.read()
                except Exception as e:
                    logger.warning("[字幕] 读取失败 %s: %s", vtt_path, e)
                    continue
            except Exception as e:
                logger.warning("[字幕] 读取失败 %s: %s", vtt_path, e)
                continue

            lrc_content = convert_vtt_to_lrc(vtt_content)
            if not lrc_content.strip():
                logger.info("[字幕] 转换后为空: %s，跳过", vtt_path)
                continue

            try:
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(lrc_content)
                converted.append(lrc_path)
                logger.info("[字幕] 已转换: %s → %s", vtt_path, lrc_path)

                # 删除原 .vtt 文件
                try:
                    os.remove(vtt_path)
                    logger.info("[字幕] 已删除原文件: %s", vtt_path)
                except Exception as e:
                    logger.warning("[字幕] 删除原文件失败 %s: %s", vtt_path, e)
            except Exception as e:
                logger.error("[字幕] 写入失败 %s: %s", lrc_path, e)

    if converted:
        logger.info("[字幕] 转换完成: %d 个文件", len(converted))
    return converted
