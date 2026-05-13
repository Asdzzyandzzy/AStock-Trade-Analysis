"""Dashboard 页面模块。

每个 render_* 函数对应一个业务页面。页面层只做展示和轻量交互，
核心计算交给 analysis，数据获取交给 data。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis.prediction import estimate_price_range
from src.analysis.scoring import comprehensive_score
from src.analysis.signals import generate_signals
from src.analysis.technical import risk_statistics, support_resistance
from src.ui.charts import financial_trend_chart, fund_flow_chart, indicator_chart, price_chart, return_distribution_chart
from src.utils.formatters import format_amount, format_number, format_percent


def _spot_row(spot_df: pd.DataFrame, code: str) -> pd.Series | None:
    if spot_df.empty or "code" not in spot_df.columns:
        return None
    rows = spot_df[spot_df["code"] == code]
    if rows.empty:
        return None
    return rows.iloc[0]


def _find_col(df: pd.DataFrame, keywords: list[str]) -> str | None:
    """在 AKShare 财务表中按关键词寻找字段。

    财务字段经常是中文长字段名，且不同版本可能略有差异。
    页面层用关键词寻找，可以在字段变化时尽量保留展示能力。
    """

    for column in df.columns:
        if all(keyword in str(column) for keyword in keywords):
            return str(column)
    return None


def _latest_financial_value(df: pd.DataFrame, keywords: list[str]):
    """获取最近一期财务字段值，识别不到时返回 None。"""

    column = _find_col(df, keywords)
    if column is None or df.empty:
        return None
    value = df[column].dropna().tail(1)
    if value.empty:
        return None
    return value.iloc[0]


def render_overview(stock, spot_df: pd.DataFrame, index_df: pd.DataFrame, industry_df: pd.DataFrame) -> None:
    """首页概览。"""

    row = _spot_row(spot_df, stock.code)
    st.subheader("首页概览")
    if row is None:
        st.warning("未在实时行情列表中匹配到该股票。请检查代码，或稍后重试 AKShare 行情接口。")
    else:
        st.caption(f"{row.get('name', stock.name)} / {stock.market_code.upper()}")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("最新价", format_number(row.get("latest_price")), format_percent(row.get("pct_change")))
        col2.metric("成交额", format_amount(row.get("amount")))
        col3.metric("总市值", format_amount(row.get("market_cap")))
        col4.metric("换手率", format_percent(row.get("turnover_rate")))
        col5.metric("市盈率TTM", format_number(row.get("pe_ttm")))
        col6.metric("市净率", format_number(row.get("pb")))

    st.markdown("#### 主要指数")
    targets = ["000001", "399001", "399006"]
    code_col = "simple_code" if "simple_code" in index_df.columns else "code"
    index_show = index_df[index_df[code_col].isin(targets)].copy() if not index_df.empty and code_col in index_df.columns else pd.DataFrame()
    if index_show.empty:
        st.info("指数接口暂未返回上证、深证、创业板数据。")
    else:
        cols = st.columns(len(index_show))
        for col, (_, item) in zip(cols, index_show.iterrows()):
            col.metric(item["name"], format_number(item.get("latest_price")), format_percent(item.get("pct_change")))

    st.markdown("#### 行业热度")
    if industry_df.empty:
        st.info("行业板块数据暂不可用。")
    else:
        top_industry = industry_df.sort_values("pct_change", ascending=False).head(8)
        st.dataframe(
            top_industry[["industry", "pct_change", "turnover_rate", "up_count", "down_count"]].rename(
                columns={"industry": "行业", "pct_change": "涨跌幅", "turnover_rate": "换手率", "up_count": "上涨家数", "down_count": "下跌家数"}
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_market_analysis(price_df: pd.DataFrame, show_ma: bool, show_boll: bool) -> None:
    """行情分析页面。"""

    st.subheader("行情分析")
    if price_df.empty:
        st.warning("历史行情为空，无法绘制 K 线。")
        return

    st.plotly_chart(price_chart(price_df, show_ma=show_ma, show_boll=show_boll), use_container_width=True)
    st.plotly_chart(indicator_chart(price_df), use_container_width=True)

    levels = support_resistance(price_df)
    stats = risk_statistics(price_df)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("支撑位", format_number(levels.get("support")))
    c2.metric("压力位", format_number(levels.get("resistance")))
    c3.metric("阶段高点", format_number(levels.get("stage_high")))
    c4.metric("年化波动率", format_percent(stats.get("annual_volatility", 0) * 100))
    c5.metric("最大回撤", format_percent(stats.get("max_drawdown", 0) * 100))

    st.plotly_chart(return_distribution_chart(price_df), use_container_width=True)


def render_fundamental(spot_row: pd.Series | None, financial_df: pd.DataFrame) -> None:
    """基本面分析页面。"""

    st.subheader("基本面分析")
    if spot_row is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("市盈率TTM", format_number(spot_row.get("pe_ttm")))
        c2.metric("市净率", format_number(spot_row.get("pb")))
        c3.metric("总市值", format_amount(spot_row.get("market_cap")))
        c4.metric("流通市值", format_amount(spot_row.get("float_market_cap")))
    else:
        st.info("实时估值字段暂不可用。")

    if financial_df.empty:
        st.warning("财务指标数据暂不可用。AKShare 财务接口可能对部分股票无数据或源站暂时不可访问。")
        return

    st.markdown("#### 核心财务质量")
    f1, f2, f3, f4, f5, f6 = st.columns(6)
    f1.metric("ROE", format_percent(_latest_financial_value(financial_df, ["净资产收益率"])))
    f2.metric("ROA", format_percent(_latest_financial_value(financial_df, ["总资产", "收益率"])))
    f3.metric("毛利率", format_percent(_latest_financial_value(financial_df, ["销售毛利率"])))
    f4.metric("净利率", format_percent(_latest_financial_value(financial_df, ["销售净利率"])))
    f5.metric("资产负债率", format_percent(_latest_financial_value(financial_df, ["资产负债率"])))
    f6.metric("经营现金流", format_number(_latest_financial_value(financial_df, ["经营", "现金流"])))

    st.markdown("#### 财务指标原始表")
    st.dataframe(financial_df.tail(8), use_container_width=True, hide_index=True)

    date_col = "report_date"
    trend_cols = [col for col in financial_df.columns if any(key in str(col) for key in ["净资产收益率", "销售毛利率", "净利润", "营业收入", "资产负债率"])][:5]
    if date_col in financial_df.columns and trend_cols:
        st.plotly_chart(financial_trend_chart(financial_df, date_col, trend_cols, "关键财务指标趋势"), use_container_width=True)
    else:
        st.info("未识别到适合绘图的财务指标字段，已保留原始表供查看。")


def render_sentiment(flow_df: pd.DataFrame, lhb_df: pd.DataFrame, code: str) -> None:
    """资金与市场情绪页面。"""

    st.subheader("资金与市场情绪")
    if flow_df.empty:
        st.info("个股资金流向数据暂不可用。")
    else:
        st.plotly_chart(fund_flow_chart(flow_df.tail(60)), use_container_width=True)
        st.dataframe(flow_df.tail(20), use_container_width=True, hide_index=True)

    st.markdown("#### 龙虎榜")
    if lhb_df.empty:
        st.info("龙虎榜接口暂未返回数据。")
    else:
        matched = lhb_df[lhb_df.astype(str).apply(lambda row: code in " ".join(row.values), axis=1)]
        if matched.empty:
            st.info("最近龙虎榜中未发现当前股票记录，这通常表示该股近期没有达到上榜条件。")
        else:
            st.dataframe(matched.head(20), use_container_width=True, hide_index=True)


def render_signals_and_score(price_df: pd.DataFrame, spot_row: pd.Series | None, financial_df: pd.DataFrame) -> None:
    """技术信号和综合评分页面。"""

    st.subheader("技术信号与综合评分")
    score = comprehensive_score(price_df, spot_row, financial_df)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("综合评分", f"{score['total']}/100")
    c2.metric("趋势评分", score["trend"])
    c3.metric("动量评分", score["momentum"])
    c4.metric("风险评分", score["risk"])
    c5.metric("基本面评分", score["fundamental"])

    st.markdown(f"**趋势状态：** {score['trend_state']}　　**风险等级：** {score['risk_level']}")
    if score["notes"]:
        st.info("；".join(score["notes"]))

    signals = generate_signals(price_df)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 看多因素")
        for item in signals["bullish"]:
            st.write(f"- {item}")
    with col2:
        st.markdown("#### 看空因素")
        for item in signals["bearish"]:
            st.write(f"- {item}")
    with col3:
        st.markdown("#### 风险提示")
        if signals["risks"]:
            for item in signals["risks"]:
                st.write(f"- {item}")
        else:
            st.write("- 暂无额外风险提示，但仍需关注大盘、行业和公告。")


def render_prediction(price_df: pd.DataFrame) -> None:
    """谨慎预测页面。"""

    st.subheader("谨慎预测与风险区间")
    estimate = estimate_price_range(price_df)
    if "low" not in estimate:
        st.info(str(estimate["message"]))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("当前价", format_number(estimate["latest_price"]))
    c2.metric("区间下沿", format_number(estimate["low"]))
    c3.metric("区间上沿", format_number(estimate["high"]))
    c4.metric("方向分类", str(estimate["direction"]))
    st.warning("仅供研究，不构成投资建议。该模块只基于历史波动率估计风险区间，无法预测政策、公告、流动性冲击等突发事件。")
