"""A 股个人投研 Dashboard 入口。

app.py 只负责：
1. 页面基础配置；
2. 侧边栏参数；
3. 调用数据层、分析层和页面模块。

真正的数据清洗、指标计算、图表绘制都放在 src 目录下，避免把所有逻辑塞进一个文件。
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from src.analysis.technical import add_technical_indicators
from src.data.akshare_client import (
    load_financial_indicator,
    load_fund_flow,
    load_index_spot,
    load_industry_board,
    load_lhb_latest,
    load_stock_history,
    load_stock_spot,
    normalize_stock_code,
)
from src.data.models import StockIdentity
from src.ui.pages import (
    _spot_row,
    render_fundamental,
    render_market_analysis,
    render_overview,
    render_prediction,
    render_sentiment,
    render_signals_and_score,
)
from src.ui.theme import apply_theme


st.set_page_config(page_title="A 股个人投研 Dashboard", page_icon="📈", layout="wide")
apply_theme()

def resolve_stock(raw_input: str, spot_df) -> StockIdentity:
    """根据代码或名称解析股票。

    用户可能输入“600519”，也可能输入“贵州茅台”。如果实时行情表可用，
    我们优先在全市场列表里搜索；如果接口失败，则退回代码规则解析。
    """

    text = raw_input.strip()
    if spot_df is not None and not spot_df.empty and {"code", "name"}.issubset(spot_df.columns):
        matched = spot_df[
            (spot_df["code"].astype(str).str.contains(text, na=False, regex=False))
            | (spot_df["name"].astype(str).str.contains(text, na=False, regex=False))
        ]
        if not matched.empty:
            row = matched.iloc[0]
            base = normalize_stock_code(str(row["code"]))
            return StockIdentity(code=base.code, market_code=base.market_code, name=str(row["name"]))
    return normalize_stock_code(text)


st.title("A 股个人投研 Dashboard")
st.caption("基于 AKShare / Streamlit / Plotly 的个人股票分析平台。数据仅供学习研究，不构成投资建议。")


with st.sidebar:
    st.header("研究参数")
    raw_code = st.text_input("股票代码 / 名称", value="600519", help="支持 600519、000001、sh600519、sz000001，也可以输入股票名称关键词")
    end_date = st.date_input("结束日期", value=date.today())
    start_date = st.date_input("开始日期", value=date.today() - timedelta(days=365 * 2))
    period = st.segmented_control("K线周期", ["日线", "周线", "月线"], default="日线")
    adjust_label = st.selectbox("复权方式", ["前复权", "不复权", "后复权"], index=0)
    st.divider()
    st.subheader("指标开关")
    show_ma = st.toggle("显示均线 MA", value=True)
    show_boll = st.toggle("显示 BOLL", value=True)
    st.caption("AKShare 数据来自外部网站，接口偶尔会受源站或网络影响。")

adjust_map = {"前复权": "qfq", "不复权": "", "后复权": "hfq"}

if start_date >= end_date:
    st.error("开始日期必须早于结束日期。")
    st.stop()

with st.spinner("正在获取 AKShare 数据..."):
    spot_result = load_stock_spot()
    spot_df_for_search = spot_result.data if spot_result.ok else None
    identity = resolve_stock(raw_code, spot_df_for_search)
    index_result = load_index_spot()
    industry_result = load_industry_board()
    history_result = load_stock_history(identity.code, start_date, end_date, period, adjust=adjust_map[adjust_label])
    financial_result = load_financial_indicator(identity.code)
    fund_flow_result = load_fund_flow(identity.code)
    lhb_result = load_lhb_latest()

spot_df = spot_result.data if spot_result.ok else None
index_df = index_result.data if index_result.ok else None
industry_df = industry_result.data if industry_result.ok else None
history_df = history_result.data if history_result.ok else None
financial_df = financial_result.data if financial_result.ok else None
fund_flow_df = fund_flow_result.data if fund_flow_result.ok else None
lhb_df = lhb_result.data if lhb_result.ok else None

for result, name in [
    (spot_result, "实时行情"),
    (index_result, "指数行情"),
    (industry_result, "行业板块"),
    (history_result, "历史行情"),
    (financial_result, "财务指标"),
    (fund_flow_result, "资金流向"),
    (lhb_result, "龙虎榜"),
]:
    if not result.ok:
        st.toast(f"{name}：{result.message}", icon="⚠️")

if history_df is None or history_df.empty:
    st.error(f"历史行情获取失败：{history_result.message}")
    st.stop()

price_df = add_technical_indicators(history_df)
spot_df = spot_df if spot_df is not None else history_df.iloc[0:0]
index_df = index_df if index_df is not None else history_df.iloc[0:0]
industry_df = industry_df if industry_df is not None else history_df.iloc[0:0]
financial_df = financial_df if financial_df is not None else history_df.iloc[0:0]
fund_flow_df = fund_flow_df if fund_flow_df is not None else history_df.iloc[0:0]
lhb_df = lhb_df if lhb_df is not None else history_df.iloc[0:0]

row = _spot_row(spot_df, identity.code) if "code" in spot_df.columns else None
if row is not None:
    identity = type(identity)(code=identity.code, market_code=identity.market_code, name=str(row.get("name", "")))

tabs = st.tabs(["概览", "行情分析", "基本面", "资金情绪", "信号评分", "谨慎预测"])
with tabs[0]:
    render_overview(identity, spot_df, index_df, industry_df)
with tabs[1]:
    render_market_analysis(price_df, show_ma=show_ma, show_boll=show_boll)
with tabs[2]:
    render_fundamental(row, financial_df)
with tabs[3]:
    render_sentiment(fund_flow_df, lhb_df, identity.code)
with tabs[4]:
    render_signals_and_score(price_df, row, financial_df)
with tabs[5]:
    render_prediction(price_df)

st.divider()
st.caption("风险声明：本工具仅用于学习、研究和个人复盘，不构成任何投资建议。投资有风险，决策需独立判断。")
