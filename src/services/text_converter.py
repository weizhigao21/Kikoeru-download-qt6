import os
import logging
import zhconv

logger = logging.getLogger(__name__)

# 支持转换内容的文件扩展名
SUBTITLE_EXTENSIONS = ['.lrc', '.txt', '.srt', '.ass', '.vtt']


def convert_traditional_to_simplified(text: str) -> str:
    """将繁体中文转换为简体中文"""
    try:
        return zhconv.convert(text, 'zh-cn')
    except Exception as e:
        logger.error(f"繁简转换失败: {e}")
        return text


def convert_file_content(file_path: str) -> bool:
    """转换文件内容中的繁体字为简体字，返回是否发生了转换"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return False

        converted = convert_traditional_to_simplified(content)

        if converted != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(converted)
            return True
        return False
    except Exception as e:
        logger.error(f"转换文件内容失败 {file_path}: {e}")
        return False


def convert_filename(file_path: str) -> str:
    """转换文件名中的繁体字为简体字，返回新路径（如果重命名成功）"""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)

    converted_name = convert_traditional_to_simplified(base_name)

    if converted_name != base_name:
        new_path = os.path.join(dir_name, converted_name)
        # 避免文件名冲突
        if os.path.exists(new_path) and new_path != file_path:
            name, ext = os.path.splitext(converted_name)
            counter = 1
            while os.path.exists(os.path.join(dir_name, f"{name}_{counter}{ext}")):
                counter += 1
            new_path = os.path.join(dir_name, f"{name}_{counter}{ext}")

        try:
            os.rename(file_path, new_path)
            return new_path
        except Exception as e:
            logger.error(f"重命名文件失败 {file_path}: {e}")
            return file_path
    return file_path


def process_directory(directory: str, extensions: list = None) -> dict:
    """处理目录下的所有文件，转换繁体字为简体字

    Args:
        directory: 目录路径
        extensions: 需要转换内容的文件扩展名列表，默认为 SUBTITLE_EXTENSIONS

    Returns:
        dict: 包含转换结果的字典
            - content_converted: 内容被转换的文件列表
            - filename_converted: 文件名被转换的文件列表 [(旧路径, 新路径), ...]
            - errors: 发生错误的文件列表
    """
    if extensions is None:
        extensions = SUBTITLE_EXTENSIONS

    result = {
        'content_converted': [],
        'filename_converted': [],
        'errors': []
    }

    if not os.path.isdir(directory):
        logger.warning(f"[繁简] 目录不存在: {directory}")
        return result

    logger.info(f"[繁简] 开始扫描目录: {directory}")

    # 先收集所有文件，避免在重命名过程中遍历出错
    all_files = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            all_files.append(os.path.join(root, filename))

    for file_path in all_files:
        if not os.path.exists(file_path):
            continue

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        # 转换文件内容（仅对指定扩展名的文件）
        if ext in extensions:
            try:
                if convert_file_content(file_path):
                    result['content_converted'].append(file_path)
            except Exception as e:
                logger.error(f"[繁简] 转换内容失败 {file_path}: {e}")
                result['errors'].append(file_path)

        # 转换文件名
        try:
            new_path = convert_filename(file_path)
            if new_path != file_path:
                result['filename_converted'].append((file_path, new_path))
        except Exception as e:
            logger.error(f"[繁简] 转换文件名失败 {file_path}: {e}")
            result['errors'].append(file_path)

    if result['content_converted']:
        logger.info(f"[繁简] 内容转换完成: {len(result['content_converted'])} 个文件")
    if result['filename_converted']:
        logger.info(f"[繁简] 文件名转换完成: {len(result['filename_converted'])} 个文件")
    if not result['content_converted'] and not result['filename_converted']:
        logger.info(f"[繁简] 无需转换 (扫描了 {len(all_files)} 个文件)")

    return result
