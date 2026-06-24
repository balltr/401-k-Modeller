from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


_REQUIRED_SHEETS = {
    "Profile",
    "Contributions",
    "Tax Brackets",
    "IRS Limits",
    "Conversions",
    "Withdrawals",
}

_REQUIRED_PROFILE_FIELDS = {
    "Current Age",
    "Retirement Age",
    "Starting Balance Traditional",
    "Starting Balance Roth",
    "Expected Annual Return (%)",
    "Inflation Rate (%)",
    "Account for Inflation",
    "State Tax Rate Working (%)",
    "State Tax Rate Retirement (%)",
    "End Age",
}


@dataclass
class Profile:
    current_age: int
    retirement_age: int
    starting_balance_traditional: float
    starting_balance_roth: float
    annual_return: float        # decimal, e.g. 0.07 for 7%
    inflation_rate: float       # decimal, e.g. 0.025 for 2.5%
    account_for_inflation: bool
    state_tax_working: float    # decimal
    state_tax_retirement: float # decimal
    end_age: int


def load(path: str | Path) -> dict:
    """Read the Excel workbook and return a dict with keys:
    profile, contributions, tax_brackets, irs_limits, conversions, withdrawals.
    """
    xl = pd.ExcelFile(Path(path))

    missing_sheets = _REQUIRED_SHEETS - set(xl.sheet_names)
    if missing_sheets:
        raise ValueError(f"Workbook is missing required sheets: {missing_sheets}")

    return {
        "profile":       _load_profile(xl),
        "contributions": _load_contributions(xl),
        "tax_brackets":  _load_tax_brackets(xl),
        "irs_limits":    _load_irs_limits(xl),
        "conversions":   _load_conversions(xl),
        "withdrawals":   _load_withdrawals(xl),
    }


def _load_profile(xl: pd.ExcelFile) -> Profile:
    df = xl.parse("Profile", index_col=0)
    raw = df.iloc[:, 0].to_dict()

    missing_fields = _REQUIRED_PROFILE_FIELDS - set(raw.keys())
    if missing_fields:
        raise ValueError(f"Profile sheet is missing required fields: {missing_fields}")

    return Profile(
        current_age=int(raw["Current Age"]),
        retirement_age=int(raw["Retirement Age"]),
        starting_balance_traditional=float(raw["Starting Balance Traditional"]),
        starting_balance_roth=float(raw["Starting Balance Roth"]),
        annual_return=float(raw["Expected Annual Return (%)"]) / 100,
        inflation_rate=float(raw["Inflation Rate (%)"]) / 100,
        account_for_inflation=str(raw["Account for Inflation"]).strip().lower() == "yes",
        state_tax_working=float(raw["State Tax Rate Working (%)"]) / 100,
        state_tax_retirement=float(raw["State Tax Rate Retirement (%)"]) / 100,
        end_age=int(raw["End Age"]),
    )


def _load_contributions(xl: pd.ExcelFile) -> pd.DataFrame:
    """Returns a DataFrame indexed by Year.
    Percentage columns are converted from e.g. 8 → 0.08.
    A missing Match Cap means no cap: employer gives the full match unconditionally.
    Filing Status must be 'Single' or 'Married Filing Jointly' for each year.
    """
    df = xl.parse("Contributions")
    df.columns = df.columns.str.strip()
    for col in ["Traditional (%)", "Roth (%)"]:
        df[col] = df[col].fillna(0) / 100
    df["Employer Match (%)"] = df["Employer Match (%)"] / 100
    df["Match Cap (%)"] = df["Match Cap (%)"].fillna(float("inf"))
    non_inf = df["Match Cap (%)"] != float("inf")
    df.loc[non_inf, "Match Cap (%)"] = df.loc[non_inf, "Match Cap (%)"] / 100
    df["Filing Status"] = df["Filing Status"].str.strip()
    return df.set_index("Year")


def _load_tax_brackets(xl: pd.ExcelFile) -> pd.DataFrame:
    """Returns a DataFrame with one row per bracket.
    Rate column is converted from e.g. 22 → 0.22.
    """
    df = xl.parse("Tax Brackets")
    df.columns = df.columns.str.strip()
    df["Rate (%)"] = df["Rate (%)"] / 100
    return df


def _load_irs_limits(xl: pd.ExcelFile) -> pd.DataFrame:
    """Returns a DataFrame indexed by Year."""
    df = xl.parse("IRS Limits")
    df.columns = df.columns.str.strip()
    return df.set_index("Year")


def _load_conversions(xl: pd.ExcelFile) -> pd.DataFrame:
    """Returns a DataFrame of planned Roth conversions.
    Empty if no conversions are planned.
    """
    df = xl.parse("Conversions")
    df.columns = df.columns.str.strip()
    return df


def _load_withdrawals(xl: pd.ExcelFile) -> pd.DataFrame:
    """Returns a DataFrame indexed by Year.
    Traditional Bracket Limit (%) is converted from e.g. 22 → 0.22.
    Missing bracket limits default to 22% (standard tax-efficient threshold).
    """
    df = xl.parse("Withdrawals")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Withdrawl ($)": "Withdrawal ($)"})
    df["Traditional Bracket Limit (%)"] = df["Traditional Bracket Limit (%)"].fillna(22) / 100
    df["Filing Status"] = df["Filing Status"].str.strip()
    return df.set_index("Year")
