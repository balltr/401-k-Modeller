from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from src.modeller.loader import load
from src.modeller.model import project, project_retirement
from src.modeller import charts


st.set_page_config(
    page_title="401(k) Modeller",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("401(k) Modeller")

    uploaded_files = st.file_uploader(
        "Upload spreadsheets",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Upload one or more Excel workbooks. Multiple files are compared side by side.",
    )

    st.divider()
    st.subheader("Charts")
    show_balance       = st.checkbox("Accumulation Balance",        value=True)
    show_contributions = st.checkbox("Annual Contributions",        value=True)
    show_tax           = st.checkbox("Annual Tax",                  value=False)
    show_income        = st.checkbox("Retirement Take-Home Income", value=True)
    show_ret_balances  = st.checkbox("Retirement Balances",         value=True)


# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading scenario…")
def _load_scenario(file_bytes: bytes, filename: str):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        data = load(tmp_path)
        accum = project(data)
        retire = project_retirement(accum, data)
        return accum, retire, data["profile"]
    finally:
        os.unlink(tmp_path)


if not uploaded_files:
    st.title("401(k) Modeller")
    st.info("Upload one or more Excel spreadsheets in the sidebar to get started.")
    st.stop()


scenarios = {}
for f in uploaded_files:
    name = Path(f.name).stem.replace("_", " ").replace("-", " ").title()
    try:
        accum, retire, profile = _load_scenario(f.getvalue(), f.name)
        scenarios[name] = (accum, retire, profile)
    except Exception as e:
        st.error(f"**{f.name}**: {e}")

if not scenarios:
    st.stop()


# ── Summary cards ──────────────────────────────────────────────────────────────

st.title("401(k) Modeller")

cols = st.columns(len(scenarios))
for col, (name, (accum, retire, profile)) in zip(cols, scenarios.items()):
    with col:
        st.subheader(name)
        a_last = accum.iloc[-1]
        r_last = retire.iloc[-1] if not retire.empty else None

        st.metric("Balance at Retirement", f"${a_last['Total Balance']:,.0f}")
        st.metric("Traditional",           f"${a_last['Traditional Balance']:,.0f}")
        st.metric("Roth",                  f"${a_last['Roth Balance']:,.0f}")
        if r_last is not None:
            st.metric(
                f"Remaining at Age {profile.end_age}",
                f"${r_last['Total Balance']:,.0f}",
            )
            st.metric(
                "Avg Annual Take-Home",
                f"${retire['Net Withdrawal'].mean():,.0f}",
            )

st.divider()


# ── Charts ─────────────────────────────────────────────────────────────────────

is_multi = len(scenarios) > 1

if is_multi:
    if show_balance:
        st.plotly_chart(charts.compare_balances(scenarios), use_container_width=True)
    if show_contributions:
        st.plotly_chart(charts.compare_contributions(scenarios), use_container_width=True)
    if show_tax:
        st.plotly_chart(charts.compare_taxes(scenarios), use_container_width=True)
    if show_income:
        st.plotly_chart(charts.compare_net_withdrawal(scenarios), use_container_width=True)
    if show_ret_balances:
        st.plotly_chart(charts.compare_retirement_balances(scenarios), use_container_width=True)
else:
    name, (accum, retire, profile) = next(iter(scenarios.items()))
    if show_balance:
        st.plotly_chart(charts.balance_over_time(accum, profile), use_container_width=True)
    if show_contributions:
        st.plotly_chart(charts.contributions_per_year(accum), use_container_width=True)
    if show_tax:
        st.plotly_chart(charts.tax_over_time(accum), use_container_width=True)
    if show_income:
        st.plotly_chart(charts.retirement_income(retire, profile), use_container_width=True)
    if show_ret_balances:
        st.plotly_chart(charts.retirement_balances(retire), use_container_width=True)
