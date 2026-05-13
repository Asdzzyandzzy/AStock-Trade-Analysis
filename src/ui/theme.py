"""Streamlit 视觉样式。

样式目标是“专业、克制、适合投研”，所以使用深色金融终端风格，
但保留足够对比度，避免花哨装饰影响读数。
"""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """注入全局 CSS。"""

    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}
        [data-testid="stMetric"] {
            background: #111827;
            border: 1px solid #243244;
            border-radius: 8px;
            padding: 14px 16px;
        }
        [data-testid="stMetricLabel"] {color: #A8B3C7;}
        .section-note {
            color: #94A3B8;
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .status-box {
            border: 1px solid #26364A;
            border-radius: 8px;
            padding: 14px 16px;
            background: #0F172A;
        }
        .small-muted {color: #94A3B8; font-size: 0.85rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

