"""Plotly 图表组件。

所有图表集中在这里，页面层只负责传数据和布局。
后续如果要统一改配色、hover 模板、图例样式，只改本模块即可。
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots


TEMPLATE = "plotly_dark"
UP_COLOR = "#EF4444"
DOWN_COLOR = "#22C55E"
LINE_BLUE = "#38BDF8"
LINE_AMBER = "#F59E0B"


def price_chart(df, show_ma: bool = True, show_boll: bool = True) -> go.Figure:
    """K 线 + 成交量图。"""

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.04,
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
    )
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线",
            increasing_line_color=UP_COLOR,
            decreasing_line_color=DOWN_COLOR,
        ),
        row=1,
        col=1,
    )

    if show_ma:
        colors = {"ma5": "#FBBF24", "ma10": "#60A5FA", "ma20": "#A78BFA", "ma60": "#94A3B8"}
        for col, color in colors.items():
            if col in df.columns:
                fig.add_trace(go.Scatter(x=df["date"], y=df[col], mode="lines", name=col.upper(), line=dict(width=1.4, color=color)), row=1, col=1)

    if show_boll and {"boll_upper", "boll_mid", "boll_lower"}.issubset(df.columns):
        fig.add_trace(go.Scatter(x=df["date"], y=df["boll_upper"], mode="lines", name="BOLL上轨", line=dict(width=1, color="#64748B")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["boll_mid"], mode="lines", name="BOLL中轨", line=dict(width=1, color="#CBD5E1")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["boll_lower"], mode="lines", name="BOLL下轨", line=dict(width=1, color="#64748B")), row=1, col=1)

    volume_colors = [UP_COLOR if close >= open_ else DOWN_COLOR for open_, close in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(x=df["date"], y=df["volume"], marker_color=volume_colors, name="成交量"), row=2, col=1)
    fig.update_layout(template=TEMPLATE, height=650, margin=dict(l=10, r=10, t=45, b=10), title="价格走势与成交量", xaxis_rangeslider_visible=False, legend=dict(orientation="h"))
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    return fig


def indicator_chart(df) -> go.Figure:
    """MACD、RSI、KDJ 三联图。"""

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=("MACD", "RSI(14)", "KDJ"))
    fig.add_trace(go.Bar(x=df["date"], y=df["macd_hist"], name="MACD柱", marker_color=["#EF4444" if v >= 0 else "#22C55E" for v in df["macd_hist"].fillna(0)]), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd_diff"], name="DIF", line=dict(color=LINE_BLUE, width=1.4)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["macd_dea"], name="DEA", line=dict(color=LINE_AMBER, width=1.4)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi14"], name="RSI14", line=dict(color="#A78BFA", width=1.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#F97316", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#22C55E", row=2, col=1)

    for col, color in [("kdj_k", "#38BDF8"), ("kdj_d", "#F59E0B"), ("kdj_j", "#F43F5E")]:
        fig.add_trace(go.Scatter(x=df["date"], y=df[col], name=col.upper(), line=dict(color=color, width=1.2)), row=3, col=1)

    fig.update_layout(template=TEMPLATE, height=720, margin=dict(l=10, r=10, t=45, b=10), legend=dict(orientation="h"))
    return fig


def return_distribution_chart(df) -> go.Figure:
    """收益率分布直方图。"""

    returns = df["return"].dropna() * 100
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=returns, nbinsx=50, marker_color="#38BDF8", name="日收益率"))
    fig.update_layout(template=TEMPLATE, height=360, title="收益率分布", xaxis_title="收益率(%)", yaxis_title="频数", margin=dict(l=10, r=10, t=45, b=10))
    return fig


def financial_trend_chart(financial_df, date_col: str, value_cols: list[str], title: str) -> go.Figure:
    """财务指标趋势图。"""

    fig = go.Figure()
    for col in value_cols:
        if col in financial_df.columns:
            fig.add_trace(go.Scatter(x=financial_df[date_col], y=financial_df[col], mode="lines+markers", name=col))
    fig.update_layout(template=TEMPLATE, height=380, title=title, margin=dict(l=10, r=10, t=45, b=10), legend=dict(orientation="h"))
    return fig


def fund_flow_chart(flow_df) -> go.Figure:
    """资金流向图，自动寻找主力净流入字段。"""

    fig = go.Figure()
    candidates = [c for c in flow_df.columns if "主力" in str(c) and "净流入" in str(c)]
    for col in candidates[:3]:
        fig.add_trace(go.Bar(x=flow_df["date"], y=flow_df[col], name=str(col)))
    fig.update_layout(template=TEMPLATE, height=420, title="主力资金流向", margin=dict(l=10, r=10, t=45, b=10), legend=dict(orientation="h"))
    return fig
