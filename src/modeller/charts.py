from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .loader import Profile

# One color per scenario — cycles if there are more than 8
_PALETTE = [
    "#2196F3", "#F44336", "#4CAF50", "#FF9800",
    "#9C27B0", "#00BCD4", "#795548", "#607D8B",
]

# Type alias: {scenario_name: (results_df, profile)}
Scenarios = Dict[str, Tuple[pd.DataFrame, Profile]]


def balance_over_time(results: pd.DataFrame, profile: Profile) -> go.Figure:
    """Stacked area chart of Traditional and Roth balances over time."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=results.index,
        y=results["Traditional Balance"],
        name="Traditional (Pre-Tax)",
        stackgroup="one",
        fillcolor="rgba(33, 150, 243, 0.6)",
        line=dict(color="#2196F3"),
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Traditional: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=results.index,
        y=results["Roth Balance"],
        name="Roth (Post-Tax)",
        stackgroup="one",
        fillcolor="rgba(76, 175, 80, 0.6)",
        line=dict(color="#4CAF50"),
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Roth: $%{y:,.0f}<extra></extra>",
    ))

    if profile.account_for_inflation:
        fig.add_trace(go.Scatter(
            x=results.index,
            y=results["Real Total Balance"],
            name="Total (Today's Dollars)",
            line=dict(color="#FF9800", dash="dash", width=2),
            customdata=results["Age"],
            hovertemplate="Year %{x} (Age %{customdata})<br>Real Total: $%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title="401(k) Balance Projection",
        xaxis_title="Year",
        yaxis_title="Balance",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def contributions_per_year(results: pd.DataFrame) -> go.Figure:
    """Stacked bar chart of annual contributions by source."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=results.index,
        y=results["Traditional Contrib"],
        name="Traditional (Employee)",
        marker_color="#2196F3",
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Traditional: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=results.index,
        y=results["Roth Contrib"],
        name="Roth (Employee)",
        marker_color="#4CAF50",
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Roth: $%{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=results.index,
        y=results["Employer Match"],
        name="Employer Match",
        marker_color="#9C27B0",
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Employer Match: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title="Annual Contributions",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        barmode="stack",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def tax_over_time(results: pd.DataFrame) -> go.Figure:
    """Area chart of annual tax owed, with conversion tax layered on top if applicable."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=results.index,
        y=results["Tax Owed"],
        name="Income Tax",
        fill="tozeroy",
        fillcolor="rgba(244, 67, 54, 0.2)",
        line=dict(color="#F44336"),
        customdata=results["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Income Tax: $%{y:,.0f}<extra></extra>",
    ))

    if results["Conversion Tax"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=results.index,
            y=results["Conversion Tax"],
            name="Roth Conversion Tax",
            fill="tozeroy",
            fillcolor="rgba(255, 152, 0, 0.2)",
            line=dict(color="#FF9800"),
            customdata=results["Age"],
            hovertemplate="Year %{x} (Age %{customdata})<br>Conversion Tax: $%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title="Annual Tax Owed",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def dashboard(results: pd.DataFrame, profile: Profile) -> go.Figure:
    """All three charts combined into a single scrollable figure."""
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("Balance Projection", "Annual Contributions", "Annual Tax Owed"),
        vertical_spacing=0.1,
    )

    for trace in balance_over_time(results, profile).data:
        fig.add_trace(trace, row=1, col=1)

    for trace in contributions_per_year(results).data:
        fig.add_trace(trace, row=2, col=1)

    for trace in tax_over_time(results).data:
        fig.add_trace(trace, row=3, col=1)

    fig.update_yaxes(tickformat="$,.0f")
    fig.update_xaxes(title_text="Year", row=3, col=1)
    fig.update_layout(
        height=1100,
        hovermode="x unified",
        showlegend=True,
        barmode="stack",
    )

    return fig


# ── Scenario comparison ────────────────────────────────────────────────────────

def compare_balances(scenarios: Scenarios) -> go.Figure:
    """One total-balance line per scenario; dashed real-total if inflation is on."""
    fig = go.Figure()
    for i, (name, (results, profile)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=results.index,
            y=results["Total Balance"],
            name=name,
            legendgroup=name,
            line=dict(color=color, width=2),
            customdata=results["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Total: $%{{y:,.0f}}<extra></extra>",
        ))
        if profile.account_for_inflation:
            fig.add_trace(go.Scatter(
                x=results.index,
                y=results["Real Total Balance"],
                name=f"{name} (Today's $)",
                legendgroup=name,
                line=dict(color=color, width=1, dash="dash"),
                customdata=results["Age"],
                hovertemplate=f"{name} (Real)<br>Year %{{x}} (Age %{{customdata}})<br>Real: $%{{y:,.0f}}<extra></extra>",
            ))
    fig.update_layout(
        title="401(k) Balance Comparison",
        xaxis_title="Year",
        yaxis_title="Balance",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def compare_contributions(scenarios: Scenarios) -> go.Figure:
    """Total annual contributions (employee + employer) per scenario."""
    fig = go.Figure()
    for i, (name, (results, _)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        total = results["Traditional Contrib"] + results["Roth Contrib"] + results["Employer Match"]
        fig.add_trace(go.Scatter(
            x=results.index,
            y=total,
            name=name,
            legendgroup=name,
            showlegend=False,   # already shown in balance panel
            line=dict(color=color, width=2),
            customdata=results["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Contributions: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Annual Contributions Comparison",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
    )
    return fig


def compare_taxes(scenarios: Scenarios) -> go.Figure:
    """Annual tax owed per scenario."""
    fig = go.Figure()
    for i, (name, (results, _)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=results.index,
            y=results["Tax Owed"],
            name=name,
            legendgroup=name,
            showlegend=False,   # already shown in balance panel
            line=dict(color=color, width=2),
            customdata=results["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Tax: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Annual Tax Comparison",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
    )
    return fig


def compare_dashboard(scenarios: Scenarios) -> go.Figure:
    """Balance, contributions, and tax comparison in one scrollable figure."""
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("Balance Projection", "Annual Contributions", "Annual Tax Owed"),
        vertical_spacing=0.1,
    )
    for trace in compare_balances(scenarios).data:
        fig.add_trace(trace, row=1, col=1)
    for trace in compare_contributions(scenarios).data:
        fig.add_trace(trace, row=2, col=1)
    for trace in compare_taxes(scenarios).data:
        fig.add_trace(trace, row=3, col=1)

    fig.update_yaxes(tickformat="$,.0f")
    fig.update_xaxes(title_text="Year", row=3, col=1)
    fig.update_layout(
        height=1100,
        hovermode="x unified",
        showlegend=True,
    )
    return fig
