"""技术信号系统。

信号用于把指标翻译成人能读懂的“看多因素、看空因素、风险提示”。
它不是交易建议，只是帮助用户快速定位值得继续研究的现象。
"""

from __future__ import annotations

import pandas as pd

from src.analysis.technical import latest_cross


def generate_signals(df: pd.DataFrame) -> dict[str, list[str] | str]:
    """根据最新行情生成技术信号。"""

    bullish: list[str] = []
    bearish: list[str] = []
    risks: list[str] = []

    if df.empty or len(df) < 30:
        return {
            "trend": "数据不足",
            "bullish": [],
            "bearish": [],
            "risks": ["历史数据太少，暂不生成技术信号。"],
        }

    latest = df.iloc[-1]

    ma_cross = latest_cross(df["ma5"], df["ma20"])
    if ma_cross == "金叉":
        bullish.append("MA5 上穿 MA20，短线趋势出现转强迹象。")
    elif ma_cross == "死叉":
        bearish.append("MA5 下穿 MA20，短线趋势转弱。")

    macd_cross = latest_cross(df["macd_diff"], df["macd_dea"])
    if macd_cross == "金叉":
        bullish.append("MACD DIF 上穿 DEA，动量边际改善。")
    elif macd_cross == "死叉":
        bearish.append("MACD DIF 下穿 DEA，动量边际走弱。")

    if latest.get("ma5", 0) > latest.get("ma10", 0) > latest.get("ma20", 0) > latest.get("ma60", 0):
        bullish.append("短中长期均线呈多头排列，趋势结构较强。")
        trend = "强势"
    elif latest.get("ma5", 0) < latest.get("ma10", 0) < latest.get("ma20", 0) < latest.get("ma60", 0):
        bearish.append("均线呈空头排列，趋势结构偏弱。")
        trend = "弱势"
    else:
        trend = "中性"

    rsi = latest.get("rsi14")
    if pd.notna(rsi):
        if rsi >= 70:
            risks.append("RSI 高于 70，短期可能存在过热和回撤压力。")
        elif rsi <= 30:
            bullish.append("RSI 低于 30，短期可能进入超卖修复区。")

    if latest.get("close", 0) > latest.get("boll_upper", float("inf")):
        bullish.append("收盘价突破布林上轨，价格强度较高。")
        risks.append("突破上轨后波动可能放大，追高风险上升。")
    elif latest.get("close", 0) < latest.get("boll_lower", 0):
        bearish.append("收盘价跌破布林下轨，短期弱势明显。")

    volume_ratio = latest.get("volume_ratio_20")
    if pd.notna(volume_ratio) and volume_ratio >= 1.8:
        if latest.get("return", 0) > 0:
            bullish.append("成交量显著高于 20 日均量，且价格上涨，存在放量突破迹象。")
        else:
            risks.append("放量下跌，说明抛压或分歧明显放大。")

    if not bullish:
        bullish.append("暂无明确看多信号，建议等待更清晰的趋势确认。")
    if not bearish:
        bearish.append("暂无明确看空信号，但仍需结合大盘和基本面验证。")

    return {"trend": trend, "bullish": bullish, "bearish": bearish, "risks": risks}

