from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .loader import Profile

# One color per scenario — cycles if there are more than 8
_PALETTE = [
    "#2196F3", "#F44336", "#4CAF50", "#FF9800",
    "#9C27B0", "#00BCD4", "#795548", "#607D8B",
]

# Type alias: {scenario_name: (accumulation_df, retirement_df, profile)}
# retirement_df may be None if the retirement phase has not been projected yet.
Scenarios = Dict[str, Tuple[pd.DataFrame, Optional[pd.DataFrame], Profile]]


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
    """One total-balance line per scenario (accumulation phase only)."""
    fig = go.Figure()
    for i, (name, (accum, _, profile)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=accum.index,
            y=accum["Total Balance"],
            name=name,
            legendgroup=name,
            line=dict(color=color, width=2),
            customdata=accum["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Total: $%{{y:,.0f}}<extra></extra>",
        ))
        if profile.account_for_inflation:
            fig.add_trace(go.Scatter(
                x=accum.index,
                y=accum["Real Total Balance"],
                name=f"{name} (Today's $)",
                legendgroup=name,
                line=dict(color=color, width=1, dash="dash"),
                customdata=accum["Age"],
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
    for i, (name, (accum, _, __)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        total = accum["Traditional Contrib"] + accum["Roth Contrib"] + accum["Employer Match"]
        fig.add_trace(go.Scatter(
            x=accum.index,
            y=total,
            name=name,
            legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
            customdata=accum["Age"],
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
    """Annual tax owed during accumulation per scenario."""
    fig = go.Figure()
    for i, (name, (accum, _, __)) in enumerate(scenarios.items()):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=accum.index,
            y=accum["Tax Owed"],
            name=name,
            legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
            customdata=accum["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Tax: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Annual Tax Comparison (Accumulation)",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
    )
    return fig


def compare_net_withdrawal(scenarios: Scenarios) -> go.Figure:
    """Net after-tax annual withdrawal per scenario — the key retirement comparison."""
    fig = go.Figure()
    for i, (name, (_, retire, profile)) in enumerate(scenarios.items()):
        if retire is None:
            continue
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=retire.index,
            y=retire["Net Withdrawal"],
            name=name,
            legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
            customdata=retire["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Take-Home: $%{{y:,.0f}}<extra></extra>",
        ))
        if profile.account_for_inflation:
            fig.add_trace(go.Scatter(
                x=retire.index,
                y=retire["Real Net Withdrawal"],
                name=f"{name} (Today's $)",
                legendgroup=name,
                showlegend=False,
                line=dict(color=color, width=1, dash="dash"),
                customdata=retire["Age"],
                hovertemplate=f"{name} (Real)<br>Year %{{x}} (Age %{{customdata}})<br>Take-Home (Real): $%{{y:,.0f}}<extra></extra>",
            ))
    fig.update_layout(
        title="Annual Retirement Take-Home Income",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
    )
    return fig


def compare_retirement_balances(scenarios: Scenarios) -> go.Figure:
    """Retirement account balance depletion per scenario."""
    fig = go.Figure()
    for i, (name, (_, retire, __)) in enumerate(scenarios.items()):
        if retire is None:
            continue
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=retire.index,
            y=retire["Total Balance"],
            name=name,
            legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
            customdata=retire["Age"],
            hovertemplate=f"{name}<br>Year %{{x}} (Age %{{customdata}})<br>Balance: $%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Retirement Balance Over Time",
        xaxis_title="Year",
        yaxis_title="Balance",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
    )
    return fig


def compare_dashboard(scenarios: Scenarios) -> go.Figure:
    """Four-panel comparison: accumulation balance, contributions,
    net withdrawal, and retirement balance depletion.
    """
    fig = make_subplots(
        rows=4,
        cols=1,
        subplot_titles=(
            "Accumulation Balance",
            "Annual Contributions",
            "Annual Retirement Take-Home Income",
            "Retirement Balance",
        ),
        vertical_spacing=0.08,
    )
    for trace in compare_balances(scenarios).data:
        fig.add_trace(trace, row=1, col=1)
    for trace in compare_contributions(scenarios).data:
        fig.add_trace(trace, row=2, col=1)
    for trace in compare_net_withdrawal(scenarios).data:
        fig.add_trace(trace, row=3, col=1)
    for trace in compare_retirement_balances(scenarios).data:
        fig.add_trace(trace, row=4, col=1)

    fig.update_yaxes(tickformat="$,.0f")
    fig.update_xaxes(title_text="Year", row=4, col=1)
    fig.update_layout(
        height=1400,
        hovermode="x unified",
        showlegend=True,
    )
    return fig


# ── Single-scenario retirement charts ─────────────────────────────────────────

def retirement_income(retire: pd.DataFrame, profile: Profile) -> go.Figure:
    """Gross withdrawal vs net after-tax withdrawal — the tax drag is the gap."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=retire.index,
        y=retire["Gross Withdrawal"],
        name="Gross Withdrawal",
        line=dict(color="#9C27B0", width=2, dash="dot"),
        customdata=retire["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Gross: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=retire.index,
        y=retire["Net Withdrawal"],
        name="Take-Home Income",
        fill="tonexty",
        fillcolor="rgba(244, 67, 54, 0.15)",
        line=dict(color="#4CAF50", width=2),
        customdata=retire["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Take-Home: $%{y:,.0f}<extra></extra>",
    ))
    if profile.account_for_inflation:
        fig.add_trace(go.Scatter(
            x=retire.index,
            y=retire["Real Net Withdrawal"],
            name="Take-Home (Today's $)",
            line=dict(color="#4CAF50", width=1, dash="dash"),
            customdata=retire["Age"],
            hovertemplate="Year %{x} (Age %{customdata})<br>Real Net: $%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title="Retirement Income (Tax Drag = Shaded Area)",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def retirement_balances(retire: pd.DataFrame) -> go.Figure:
    """Stacked area showing Traditional and Roth balance depletion in retirement."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=retire.index,
        y=retire["Traditional Balance"],
        name="Traditional (Pre-Tax)",
        stackgroup="one",
        fillcolor="rgba(33, 150, 243, 0.6)",
        line=dict(color="#2196F3"),
        customdata=retire["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Traditional: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=retire.index,
        y=retire["Roth Balance"],
        name="Roth (Post-Tax)",
        stackgroup="one",
        fillcolor="rgba(76, 175, 80, 0.6)",
        line=dict(color="#4CAF50"),
        customdata=retire["Age"],
        hovertemplate="Year %{x} (Age %{customdata})<br>Roth: $%{y:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title="Retirement Balance Depletion",
        xaxis_title="Year",
        yaxis_title="Balance",
        yaxis_tickformat="$,.0f",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def retirement_dashboard(
    accum: pd.DataFrame,
    retire: pd.DataFrame,
    profile: Profile,
) -> go.Figure:
    """Full lifecycle: accumulation balance, retirement income, retirement balance."""
    fig = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=(
            "Accumulation Balance",
            "Retirement Income (Tax Drag = Shaded Area)",
            "Retirement Balance Depletion",
        ),
        vertical_spacing=0.1,
    )
    for trace in balance_over_time(accum, profile).data:
        fig.add_trace(trace, row=1, col=1)
    for trace in retirement_income(retire, profile).data:
        fig.add_trace(trace, row=2, col=1)
    for trace in retirement_balances(retire).data:
        fig.add_trace(trace, row=3, col=1)

    fig.update_yaxes(tickformat="$,.0f")
    fig.update_xaxes(title_text="Year", row=3, col=1)
    fig.update_layout(
        height=1200,
        hovermode="x unified",
        showlegend=True,
        barmode="stack",
    )
    return fig
