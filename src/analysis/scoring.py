"""综合评分系统。

评分目标不是预测股价，而是把趋势、动量、风险、基本面做成一个可解释的研究框架。
每个子评分都尽量使用透明规则，避免“黑箱神秘分数”。
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src.analysis.technical import risk_statistics


def _clip_score(value: float) -> float:
    """保证评分落在 0-100 区间。"""

    if math.isnan(value):
        return 50.0
    return float(max(0, min(100, value)))


def _latest_numeric(row: pd.Series, key: str, default: float = np.nan) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_trend(df: pd.DataFrame) -> float:
    """趋势评分：看均线排列、价格相对均线位置和阶段收益。"""

    if df.empty or len(df) < 60:
        return 50.0
    latest = df.iloc[-1]
    score = 50.0

    close = _latest_numeric(latest, "close")
    ma20 = _latest_numeric(latest, "ma20")
    ma60 = _latest_numeric(latest, "ma60")
    if close > ma20:
        score += 12
    else:
        score -= 12
    if ma20 > ma60:
        score += 14
    else:
        score -= 14

    if latest.get("ma5", 0) > latest.get("ma10", 0) > latest.get("ma20", 0) > latest.get("ma60", 0):
        score += 18
    elif latest.get("ma5", 0) < latest.get("ma10", 0) < latest.get("ma20", 0) < latest.get("ma60", 0):
        score -= 18

    recent_return = df["close"].tail(20).iloc[-1] / df["close"].tail(20).iloc[0] - 1
    score += np.clip(recent_return * 100, -15, 15)
    return _clip_score(score)


def score_momentum(df: pd.DataFrame) -> float:
    """动量评分：结合 RSI、MACD 柱和近期成交量。"""

    if df.empty or len(df) < 30:
        return 50.0
    latest = df.iloc[-1]
    score = 50.0

    rsi = _latest_numeric(latest, "rsi14")
    if pd.notna(rsi):
        if 45 <= rsi <= 65:
            score += 12
        elif 65 < rsi <= 75:
            score += 6
        elif rsi > 80:
            score -= 10
        elif rsi < 35:
            score -= 6

    macd_hist = _latest_numeric(latest, "macd_hist", 0)
    score += np.clip(macd_hist / max(latest["close"], 1) * 5000, -15, 15)

    volume_ratio = _latest_numeric(latest, "volume_ratio_20")
    if pd.notna(volume_ratio):
        if latest.get("return", 0) > 0 and volume_ratio > 1.2:
            score += min(12, (volume_ratio - 1) * 8)
        elif latest.get("return", 0) < 0 and volume_ratio > 1.5:
            score -= min(15, (volume_ratio - 1) * 10)

    return _clip_score(score)


def score_risk(df: pd.DataFrame) -> tuple[float, str]:
    """风险评分：分数越高代表风险越低。"""

    stats = risk_statistics(df)
    if not stats:
        return 50.0, "中"

    score = 80.0
    volatility = stats["annual_volatility"]
    max_drawdown = abs(stats["max_drawdown"])

    score -= min(35, volatility * 100 * 0.8)
    score -= min(35, max_drawdown * 100 * 1.1)

    latest = df.iloc[-1]
    if latest.get("return", 0) < -0.04 and latest.get("volume_ratio_20", 1) > 1.5:
        score -= 12

    final = _clip_score(score)
    if final >= 70:
        level = "低"
    elif final >= 45:
        level = "中"
    else:
        level = "高"
    return final, level


def _find_financial_column(financial_df: pd.DataFrame, keywords: list[str]) -> str | None:
    """按关键词寻找财务字段。

    AKShare 财务字段多为中文，且不同版本可能略有差异。关键词匹配比硬编码一两个列名更稳健。
    """

    for column in financial_df.columns:
        if all(keyword in str(column) for keyword in keywords):
            return str(column)
    return None


def score_fundamental(spot_row: pd.Series | None, financial_df: pd.DataFrame | None) -> tuple[float, list[str]]:
    """基本面评分：估值 + 盈利质量 + 成长性。

    如果财务数据缺失，不伪造结论，而是返回中性分并附带说明。
    """

    notes: list[str] = []
    score = 50.0

    if spot_row is not None and not spot_row.empty:
        pe = _latest_numeric(spot_row, "pe_ttm")
        pb = _latest_numeric(spot_row, "pb")
        if pd.notna(pe) and pe > 0:
            if pe < 15:
                score += 8
            elif pe > 60:
                score -= 10
        else:
            notes.append("市盈率缺失或为负，估值评分采用中性处理。")
        if pd.notna(pb) and pb > 0:
            if pb < 2:
                score += 6
            elif pb > 8:
                score -= 8

    if financial_df is None or financial_df.empty:
        notes.append("财务指标接口未返回有效数据，基本面评分主要依据实时估值字段。")
        return _clip_score(score), notes

    latest = financial_df.dropna(how="all").tail(1)
    if latest.empty:
        notes.append("财务指标为空，基本面评分采用中性处理。")
        return _clip_score(score), notes
    row = latest.iloc[0]

    roe_col = _find_financial_column(financial_df, ["净资产收益率"])
    gross_col = _find_financial_column(financial_df, ["销售毛利率"])
    profit_growth_col = _find_financial_column(financial_df, ["净利润", "增长率"])

    if roe_col:
        roe = _latest_numeric(row, roe_col)
        if pd.notna(roe):
            score += np.clip((roe - 8) * 1.2, -12, 18)
    else:
        notes.append("未识别到 ROE 字段。")

    if gross_col:
        gross_margin = _latest_numeric(row, gross_col)
        if pd.notna(gross_margin):
            score += np.clip((gross_margin - 20) * 0.25, -8, 10)

    if profit_growth_col:
        growth = _latest_numeric(row, profit_growth_col)
        if pd.notna(growth):
            score += np.clip(growth * 0.25, -12, 15)
    else:
        notes.append("未识别到净利润增长字段。")

    return _clip_score(score), notes


def comprehensive_score(df: pd.DataFrame, spot_row: pd.Series | None, financial_df: pd.DataFrame | None) -> dict[str, Any]:
    """输出完整评分结果。

    权重设计：
    - 趋势 35%：技术分析里趋势最重要；
    - 动量 25%：用于观察趋势是否还在加速；
    - 风险 20%：高波动和大回撤会降低可操作性；
    - 基本面 20%：个人投研不能只看图，也要看估值和质量。
    """

    trend = score_trend(df)
    momentum = score_momentum(df)
    risk, risk_level = score_risk(df)
    fundamental, notes = score_fundamental(spot_row, financial_df)
    total = trend * 0.35 + momentum * 0.25 + risk * 0.2 + fundamental * 0.2

    if trend >= 70:
        trend_state = "强势"
    elif trend >= 45:
        trend_state = "中性"
    else:
        trend_state = "弱势"

    return {
        "total": round(float(total), 1),
        "trend": round(trend, 1),
        "momentum": round(momentum, 1),
        "risk": round(risk, 1),
        "fundamental": round(fundamental, 1),
        "trend_state": trend_state,
        "risk_level": risk_level,
        "notes": notes,
    }
