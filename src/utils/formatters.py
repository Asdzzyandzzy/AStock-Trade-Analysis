"""页面展示用格式化函数。

数据层统一保留原始数值，展示层再格式化为“亿、万、百分比”等形式。
这样可以避免计算时把字符串当成数字，也方便以后导出干净的数据。
"""

from __future__ import annotations

import math
from typing import Any


def is_missing(value: Any) -> bool:
    """判断值是否缺失。

    pandas/numpy 的缺失值有多种表示方式，集中处理可以减少页面上的重复判断。
    """

    try:
        return value is None or (isinstance(value, float) and math.isnan(value))
    except TypeError:
        return True


def format_number(value: Any, digits: int = 2, empty: str = "--") -> str:
    """把普通数字格式化为适合 metric 卡片展示的字符串。"""

    if is_missing(value):
        return empty
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return empty


def format_percent(value: Any, digits: int = 2, empty: str = "--") -> str:
    """格式化百分比。

    AKShare 的多数涨跌幅字段已经是百分数，例如 3.2 表示 3.2%，所以这里不再乘 100。
    """

    if is_missing(value):
        return empty
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return empty


def format_amount(value: Any, digits: int = 2, empty: str = "--") -> str:
    """把金额转换为中文金融终端常见单位。"""

    if is_missing(value):
        return empty
    try:
        number = float(value)
    except (TypeError, ValueError):
        return empty

    abs_number = abs(number)
    if abs_number >= 100_000_000:
        return f"{number / 100_000_000:.{digits}f} 亿"
    if abs_number >= 10_000:
        return f"{number / 10_000:.{digits}f} 万"
    return f"{number:,.{digits}f}"

