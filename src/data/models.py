"""轻量数据模型。

这里没有引入复杂 ORM，只用 dataclass 表示页面需要的核心信息。
这样对初学者更友好，也便于 IDE 自动提示字段含义。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockIdentity:
    """股票身份信息。

    code: 六位 A 股代码，例如 600519。
    market_code: 带交易所前缀的代码，例如 sh600519，主要用于部分 AKShare 接口。
    name: 股票名称，未匹配到时为空字符串。
    """

    code: str
    market_code: str
    name: str = ""


@dataclass(frozen=True)
class DataResult:
    """统一的数据返回结构。

    ok 为 False 时，data 通常为空，message 会说明失败原因。
    页面层据此展示友好提示，而不是让异常直接打断整个 Dashboard。
    """

    ok: bool
    data: object
    message: str = ""
