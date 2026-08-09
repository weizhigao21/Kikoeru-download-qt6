"""公共工具函数。"""

import re

# 匹配 RJ/rj/RG/rg 前缀（大小写敏感地覆盖常见变体）
_RJ_PREFIX_RE = re.compile(r'^(?:RJ|rj|RG|rg)')


def normalize_rj_id(rj_id) -> str:
    """将 RJ ID 规范化为 6 位数字字符串（无前缀）。

    例：
        "RJ10101"  -> "010101"
        "rj010101" -> "010101"
        "RG010101" -> "010101"
        "12345"    -> "012345"

    Args:
        rj_id: 原始 ID，可为字符串或数字。

    Returns:
        6 位数字字符串；输入为空时返回空串。
    """
    if not rj_id:
        return ""
    return _RJ_PREFIX_RE.sub('', str(rj_id)).strip().zfill(6)


def strip_rj_prefix(rj_id) -> str:
    """去除 RJ/rj/RG/rg 前缀，返回纯数字字符串（无零填充）。

    用于 API 请求路径中的数字 ID（如 workInfo/{rid}、tracks/{rid}）。

    例：
        "RJ10101"  -> "10101"
        "rj010101" -> "10101"
        "12345"    -> "12345"
    """
    if not rj_id:
        return ""
    return str(int(_RJ_PREFIX_RE.sub('', str(rj_id)).strip()))
