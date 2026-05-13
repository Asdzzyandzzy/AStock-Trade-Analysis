"""AKShare 数据访问层。

本模块只做三件事：
1. 调用 AKShare 官方接口；
2. 把中文字段清洗成项目内部统一英文字段；
3. 捕获异常并返回友好的 DataResult。

页面和分析模块都不直接调用 AKShare。这样做的好处是：如果某个接口未来字段变化，
我们只需要改这里，不会牵连整套 Dashboard。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import akshare as ak
import pandas as pd
import streamlit as st

from src.data.models import DataResult, StockIdentity
from src.utils.logger import logger


PERIOD_MAP = {"日线": "daily", "周线": "weekly", "月线": "monthly"}


def normalize_stock_code(raw_code: str) -> StockIdentity:
    """把用户输入统一为六位代码和带市场前缀代码。

    支持示例：
    - 600519 -> sh600519
    - sh600519 -> sh600519
    - 000001 -> sz000001

    A 股常见规则：600/601/603/605/688 开头多为沪市，000/001/002/003/300 开头多为深市。
    北交所代码也可展示，但本项目主线偏沪深 A 股。
    """

    code = str(raw_code).strip().lower().replace(".", "")
    if code.startswith(("sh", "sz", "bj")):
        prefix, six_code = code[:2], code[2:]
    else:
        six_code = "".join(ch for ch in code if ch.isdigit())[-6:].zfill(6)
        if six_code.startswith(("6", "9")):
            prefix = "sh"
        elif six_code.startswith(("8", "4")):
            prefix = "bj"
        else:
            prefix = "sz"
    return StockIdentity(code=six_code, market_code=f"{prefix}{six_code}")


def _safe_call(func: Callable, *args, default=None, **kwargs) -> DataResult:
    """统一捕获 AKShare 调用异常。

    AKShare 的数据源来自多个网站，接口可用性受网络和源站影响。统一封装后，
    页面可以继续显示其他模块，而不是因为一个接口失败整体崩溃。
    """

    try:
        data = func(*args, **kwargs)
        if isinstance(data, pd.DataFrame) and data.empty:
            return DataResult(False, default if default is not None else data, "接口返回为空数据")
        return DataResult(True, data, "")
    except Exception as exc:  # noqa: BLE001 - 页面型应用需要兜底所有外部接口异常
        logger.exception("AKShare 接口调用失败: %s", getattr(func, "__name__", func))
        return DataResult(False, default, f"数据接口暂时不可用：{exc}")


def _to_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """把指定列转为数值，无法转换的值设为 NaN。"""

    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_stock_spot() -> DataResult:
    """获取沪深京 A 股实时行情。

    选择 stock_zh_a_spot_em 的原因：
    - 东财源字段完整，包含成交额、换手率、市盈率、市净率、市值等 Dashboard 关键字段；
    - 单次返回全市场，适合做股票搜索和概览；
    - 官方文档中该接口字段说明清晰。
    """

    result = _safe_call(ak.stock_zh_a_spot_em, default=pd.DataFrame())
    if not result.ok:
        return result

    df = result.data.copy()
    rename_map = {
        "代码": "code",
        "名称": "name",
        "最新价": "latest_price",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "最高": "high",
        "最低": "low",
        "今开": "open",
        "昨收": "prev_close",
        "量比": "volume_ratio",
        "换手率": "turnover_rate",
        "市盈率-动态": "pe_ttm",
        "市净率": "pb",
        "总市值": "market_cap",
        "流通市值": "float_market_cap",
    }
    df = df.rename(columns=rename_map)
    numeric_cols = [col for col in rename_map.values() if col not in {"code", "name"}]
    df = _to_numeric(df, numeric_cols)
    df["code"] = df["code"].astype(str).str.zfill(6)
    return DataResult(True, df, "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_stock_history(code: str, start: date, end: date, period_label: str, adjust: str = "qfq") -> DataResult:
    """获取个股历史行情并统一为 OHLCV 字段。

    period_label 使用中文是为了 UI 友好，内部再映射为 AKShare 需要的 daily/weekly/monthly。
    adjust 默认前复权，适合做长期技术分析；短线看盘可在侧边栏切换为不复权。
    """

    identity = normalize_stock_code(code)
    period = PERIOD_MAP.get(period_label, "daily")
    result = _safe_call(
        ak.stock_zh_a_hist,
        symbol=identity.code,
        period=period,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust=adjust,
        default=pd.DataFrame(),
    )
    if not result.ok:
        return result

    df = result.data.copy()
    df = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover_rate",
        }
    )
    numeric_cols = ["open", "close", "high", "low", "volume", "amount", "amplitude", "pct_change", "change", "turnover_rate"]
    df = _to_numeric(df, numeric_cols)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return DataResult(True, df, "")


@st.cache_data(ttl=300, show_spinner=False)
def load_index_spot() -> DataResult:
    """获取沪深重要指数实时行情，用于首页市场温度计。"""

    result = _safe_call(ak.stock_zh_index_spot_em, symbol="沪深重要指数", default=pd.DataFrame())
    if not result.ok:
        return result
    df = result.data.copy().rename(
        columns={
            "代码": "code",
            "名称": "name",
            "最新价": "latest_price",
            "涨跌幅": "pct_change",
            "成交额": "amount",
        }
    )
    df = _to_numeric(df, ["latest_price", "pct_change", "amount"])
    df["code"] = df["code"].astype(str)
    df["simple_code"] = df["code"].str[-6:]
    return DataResult(True, df, "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_industry_board() -> DataResult:
    """获取东财行业板块实时行情。

    该数据用于行业热度和行业对比。个股所属行业在不同 AKShare 接口中并不总是稳定，
    因此这里作为辅助信息展示，而不强行虚构个股行业。
    """

    result = _safe_call(ak.stock_board_industry_name_em, default=pd.DataFrame())
    if not result.ok:
        return result
    df = result.data.copy().rename(
        columns={
            "板块名称": "industry",
            "最新价": "latest_price",
            "涨跌幅": "pct_change",
            "总市值": "market_cap",
            "换手率": "turnover_rate",
            "上涨家数": "up_count",
            "下跌家数": "down_count",
        }
    )
    df = _to_numeric(df, ["latest_price", "pct_change", "market_cap", "turnover_rate", "up_count", "down_count"])
    return DataResult(True, df, "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_financial_indicator(code: str) -> DataResult:
    """获取个股财务指标。

    使用 stock_financial_analysis_indicator 的原因是它按个股返回多期关键财务指标，
    比直接拼资产负债表/利润表更适合个人投研 Dashboard 的第一版。
    """

    identity = normalize_stock_code(code)
    result = _safe_call(ak.stock_financial_analysis_indicator, symbol=identity.code, default=pd.DataFrame())
    if not result.ok:
        return result
    df = result.data.copy()
    if "日期" in df.columns:
        df["report_date"] = pd.to_datetime(df["日期"], errors="coerce")
    else:
        df["report_date"] = pd.NaT
    # 财务指标字段在不同版本中可能略有差异，因此保留中文原列，同时额外标准化常用指标。
    for col in df.columns:
        if col != "report_date":
            df[col] = pd.to_numeric(df[col], errors="ignore")
    return DataResult(True, df.sort_values("report_date", na_position="last").reset_index(drop=True), "")


@st.cache_data(ttl=600, show_spinner=False)
def load_fund_flow(code: str) -> DataResult:
    """获取个股资金流向。

    资金流向适合作为情绪辅助指标，不能单独作为买卖依据。
    """

    identity = normalize_stock_code(code)
    result = _safe_call(ak.stock_individual_fund_flow, stock=identity.code, market=identity.market_code[:2], default=pd.DataFrame())
    if not result.ok:
        return result
    df = result.data.copy()
    df = df.rename(columns={"日期": "date"})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in df.columns:
        if column != "date":
            df[column] = pd.to_numeric(df[column], errors="ignore")
    return DataResult(True, df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True), "")


@st.cache_data(ttl=600, show_spinner=False)
def load_lhb_latest() -> DataResult:
    """获取最近龙虎榜数据。

    龙虎榜只作为市场情绪与异动参考，无法保证任意个股当日都有记录。
    """

    end = date.today()
    start = end - timedelta(days=14)
    result = _safe_call(
        ak.stock_lhb_detail_em,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        default=pd.DataFrame(),
    )
    if not result.ok:
        return result
    return DataResult(True, result.data.copy(), "")
