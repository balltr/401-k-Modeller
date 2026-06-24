from __future__ import annotations

import pandas as pd


def calculate_tax(
    taxable_income: float,
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
    state_rate: float,
) -> float:
    """Total tax owed (federal + state) on taxable_income."""
    if taxable_income <= 0:
        return 0.0
    return _federal_tax(taxable_income, year, filing_status, brackets) + taxable_income * state_rate


def marginal_rate(
    taxable_income: float,
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
) -> float:
    """Federal marginal rate — the bracket the last dollar of income falls into."""
    rows = _brackets_for_year(year, filing_status, brackets)
    for _, row in rows.iterrows():
        ceiling = row["Bracket Ceiling"]
        if pd.isna(ceiling) or taxable_income <= ceiling:
            return row["Rate (%)"]
    return rows.iloc[-1]["Rate (%)"]


def effective_rate(
    taxable_income: float,
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
    state_rate: float,
) -> float:
    """Combined effective rate — total tax divided by total income."""
    if taxable_income <= 0:
        return 0.0
    return calculate_tax(taxable_income, year, filing_status, brackets, state_rate) / taxable_income


def _federal_tax(
    taxable_income: float,
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
) -> float:
    rows = _brackets_for_year(year, filing_status, brackets)
    tax = 0.0
    for _, row in rows.iterrows():
        floor = row["Bracket Floor"]
        ceiling = row["Bracket Ceiling"]
        rate = row["Rate (%)"]
        if taxable_income <= floor:
            break
        top = taxable_income if pd.isna(ceiling) else min(taxable_income, ceiling)
        tax += (top - floor) * rate
    return tax


def max_income_in_bracket(
    rate_limit: float,
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
) -> float:
    """Return the income ceiling of the highest bracket whose rate is at or
    below rate_limit. Used to find how much Traditional can be withdrawn before
    crossing into a bracket the caller wants to avoid.

    Returns float('inf') if rate_limit is at or above the top bracket rate.
    """
    rows = _brackets_for_year(year, filing_status, brackets)
    ceiling = 0.0
    for _, row in rows.iterrows():
        if row["Rate (%)"] <= rate_limit:
            c = row["Bracket Ceiling"]
            ceiling = float("inf") if pd.isna(c) else float(c)
        else:
            break
    return ceiling


def _brackets_for_year(
    year: int,
    filing_status: str,
    brackets: pd.DataFrame,
) -> pd.DataFrame:
    """Return brackets for the closest available year at or before `year`.

    Using the most recent available year is a reasonable fallback since bracket
    thresholds change modestly from year to year and the user can always add new
    rows to the Tax Brackets sheet to get exact figures.
    """
    available = brackets.loc[brackets["Filing Status"] == filing_status, "Year"].unique()
    valid = sorted(y for y in available if y <= year)
    if not valid:
        raise ValueError(
            f"No '{filing_status}' brackets found for {year} or earlier. "
            "Add rows to the 'Tax Brackets' sheet."
        )
    closest = valid[-1]
    mask = (brackets["Year"] == closest) & (brackets["Filing Status"] == filing_status)
    return brackets[mask].reset_index(drop=True)
