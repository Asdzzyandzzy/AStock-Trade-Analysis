"""技术指标计算。

本模块只依赖标准 OHLCV 字段：date/open/high/low/close/volume/amount。
这样数据源换了也能复用指标逻辑。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    """为行情数据增加常用技术指标。

    指标说明：
    - MA: 简单移动平均线，观察趋势方向和均线排列。
    - EMA: 指数移动平均线，对最近价格反应更快。
    - MACD: 用快慢 EMA 的差观察动量变化，金叉/死叉常用于趋势确认。
    - RSI: 相对强弱指标，常用 70/30 粗略观察超买超卖。
    - BOLL: 布林带，用均线加减标准差观察价格区间和突破。
    - KDJ: 随机指标，适合辅助判断短期摆动，不适合单独决策。
    """

    df = price_df.copy()
    if df.empty:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]

    for window in [5, 10, 20, 60]:
        df[f"ma{window}"] = close.rolling(window=window, min_periods=max(2, window // 2)).mean()

    df["ema12"] = close.ewm(span=12, adjust=False).mean()
    df["ema26"] = close.ewm(span=26, adjust=False).mean()
    df["macd_diff"] = df["ema12"] - df["ema26"]
    df["macd_dea"] = df["macd_diff"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = (df["macd_diff"] - df["macd_dea"]) * 2

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=7).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=7).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - 100 / (1 + rs)

    mid = close.rolling(20, min_periods=10).mean()
    std = close.rolling(20, min_periods=10).std()
    df["boll_mid"] = mid
    df["boll_upper"] = mid + 2 * std
    df["boll_lower"] = mid - 2 * std

    low_min = low.rolling(9, min_periods=5).min()
    high_max = high.rolling(9, min_periods=5).max()
    rsv = (close - low_min) / (high_max - low_min).replace(0, np.nan) * 100
    df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
    df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
    df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

    df["return"] = close.pct_change()
    df["volume_ma20"] = df["volume"].rolling(20, min_periods=10).mean()
    df["volume_ratio_20"] = df["volume"] / df["volume_ma20"]
    return df


def support_resistance(df: pd.DataFrame, lookback: int = 120) -> dict[str, float]:
    """估算支撑位和压力位。

    这里使用最近 lookback 根 K 线的分位数，而不是寻找复杂形态。
    分位数方法可解释、稳定，也更适合初学者理解：
    - 低位 20% 分位数附近，可作为粗略支撑参考；
    - 高位 80% 分位数附近，可作为粗略压力参考。
    """

    if df.empty or "close" not in df:
        return {}
    recent = df.tail(lookback)
    return {
        "support": float(recent["low"].quantile(0.2)),
        "resistance": float(recent["high"].quantile(0.8)),
        "stage_low": float(recent["low"].min()),
        "stage_high": float(recent["high"].max()),
    }


def risk_statistics(df: pd.DataFrame) -> dict[str, float]:
    """计算收益、波动率和最大回撤。

    波动率默认年化到 252 个交易日。周线/月线下这个年化并不完全精确，
    但仍可作为相对风险参考；页面会把它作为研究指标而非确定结论。
    """

    if df.empty or "close" not in df:
        return {}
    returns = df["close"].pct_change().dropna()
    if returns.empty:
        return {}

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1
    return {
        "latest_return": float(returns.iloc[-1]),
        "period_return": float(df["close"].iloc[-1] / df["close"].iloc[0] - 1),
        "annual_volatility": float(returns.std() * np.sqrt(252)),
        "max_drawdown": float(drawdown.min()),
        "positive_days_ratio": float((returns > 0).mean()),
    }


def latest_cross(series_a: pd.Series, series_b: pd.Series) -> str:
    """判断最新一根 K 线是否发生金叉或死叉。"""

    valid = pd.concat([series_a, series_b], axis=1).dropna()
    if len(valid) < 2:
        return "数据不足"
    prev_a, prev_b = valid.iloc[-2, 0], valid.iloc[-2, 1]
    curr_a, curr_b = valid.iloc[-1, 0], valid.iloc[-1, 1]
    if prev_a <= prev_b and curr_a > curr_b:
        return "金叉"
    if prev_a >= prev_b and curr_a < curr_b:
        return "死叉"
    return "无明显交叉"
