"""谨慎预测模块。

这里不预测“明天涨到多少钱”，而是用历史收益分布估计波动区间。
这种方法透明、容易解释，也符合个人投研中更实用的风险管理思路。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_price_range(df: pd.DataFrame, horizon: int = 20) -> dict[str, float | str]:
    """基于历史日收益估计未来波动区间。

    参数 horizon 表示观察窗口，例如 20 约等于一个月交易日。
    方法：
    - 取最近 120 根 K 线的收益率；
    - 用收益率标准差乘以 sqrt(horizon) 估计区间宽度；
    - 给出 68% 粗略波动区间，而不是方向性承诺。
    """

    if df.empty or len(df) < 60:
        return {"message": "历史数据不足，暂不估计波动区间。"}

    returns = df["close"].pct_change().dropna().tail(120)
    latest_price = float(df["close"].iloc[-1])
    volatility = float(returns.std() * np.sqrt(horizon))
    drift = float(returns.mean() * horizon)

    center = latest_price * (1 + drift)
    low = center * (1 - volatility)
    high = center * (1 + volatility)

    recent_return = df["close"].tail(20).iloc[-1] / df["close"].tail(20).iloc[0] - 1
    if recent_return > 0.08 and df["ma20"].iloc[-1] > df["ma60"].iloc[-1]:
        direction = "偏强震荡"
    elif recent_return < -0.08 and df["ma20"].iloc[-1] < df["ma60"].iloc[-1]:
        direction = "偏弱震荡"
    else:
        direction = "区间震荡"

    return {
        "latest_price": latest_price,
        "low": float(low),
        "high": float(high),
        "volatility": volatility,
        "direction": direction,
        "message": "该区间来自历史波动率估计，仅用于风险研究，不构成投资建议。",
    }
