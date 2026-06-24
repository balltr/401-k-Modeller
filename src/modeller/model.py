from __future__ import annotations

import math

import pandas as pd

from . import tax as tax_module


def project(data: dict) -> pd.DataFrame:
    """Run a year-by-year 401k projection through the final year in the
    Contributions sheet. Returns one row per year indexed by Year.
    """
    profile = data["profile"]
    contributions = data["contributions"]
    brackets = data["tax_brackets"]
    irs_limits = data["irs_limits"]
    conversions = data["conversions"]

    trad_balance = profile.starting_balance_traditional
    roth_balance = profile.starting_balance_roth
    start_year = contributions.index.min()

    rows = []

    for year in contributions.index:
        c = contributions.loc[year]

        age = int(c["Age"]) if "Age" in contributions.columns else (
            profile.current_age + (year - start_year)
        )
        salary = c["Gross Salary"]
        trad_pct = c["Traditional (%)"]
        roth_pct = c["Roth (%)"]
        match_pct = c["Employer Match (%)"]
        match_cap = c["Match Cap (%)"]
        filing_status = c["Filing Status"]

        # IRS annual contribution limit (catch-up allowed at age 50+)
        limit_year = _closest_year(year, irs_limits.index)
        irs_limit = irs_limits.loc[limit_year, "Standard Limit"]
        if age >= 50:
            irs_limit += irs_limits.loc[limit_year, "Catch-Up Limit"]

        # Employee contributions — traditional is applied first against the limit
        trad_contrib = min(salary * trad_pct, irs_limit)
        roth_contrib = min(salary * roth_pct, max(0, irs_limit - trad_contrib))

        # Employer match goes into the traditional balance.
        # No cap (inf) → full match regardless of employee contribution.
        # With cap → match scales proportionally if employee contributes less than the cap.
        employee_rate = trad_pct + roth_pct
        if math.isinf(match_cap):
            employer_match = salary * match_pct
        else:
            proportion = min(employee_rate, match_cap) / match_cap if match_cap > 0 else 1.0
            employer_match = proportion * match_pct * salary

        # Traditional contributions lower taxable income; Roth do not
        taxable_income = salary - trad_contrib
        tax_owed = tax_module.calculate_tax(
            taxable_income, year, filing_status, brackets, profile.state_tax_working
        )

        # Roth conversion: the converted amount is added on top of normal income
        conversion_amount = _conversion_for_year(year, conversions)
        conversion_tax = 0.0
        if conversion_amount > 0:
            tax_with_conversion = tax_module.calculate_tax(
                taxable_income + conversion_amount,
                year,
                filing_status,
                brackets,
                profile.state_tax_working,
            )
            conversion_tax = tax_with_conversion - tax_owed

        # Contributions go in at the start of the year, then the whole balance compounds
        trad_balance = (trad_balance + trad_contrib + employer_match) * (1 + profile.annual_return)
        roth_balance = (roth_balance + roth_contrib) * (1 + profile.annual_return)

        # Roth conversion moves money from traditional to Roth after growth
        if conversion_amount > 0:
            actual_conversion = min(conversion_amount, trad_balance)
            trad_balance -= actual_conversion
            roth_balance += actual_conversion

        total_balance = trad_balance + roth_balance

        # Inflation-adjusted value expressed in start-year dollars
        years_elapsed = year - start_year
        real_total = total_balance / (1 + profile.inflation_rate) ** years_elapsed

        rows.append({
            "Year": year,
            "Age": age,
            "Gross Salary": salary,
            "Traditional Contrib": trad_contrib,
            "Roth Contrib": roth_contrib,
            "Employer Match": employer_match,
            "Taxable Income": taxable_income,
            "Tax Owed": tax_owed,
            "Conversion Amount": conversion_amount,
            "Conversion Tax": conversion_tax,
            "Traditional Balance": trad_balance,
            "Roth Balance": roth_balance,
            "Total Balance": total_balance,
            "Real Total Balance": real_total,
        })

    return pd.DataFrame(rows).set_index("Year")


def _closest_year(year: int, index: pd.Index) -> int:
    """Return the most recent available year at or before `year`."""
    valid = [y for y in index if y <= year]
    if not valid:
        raise ValueError(f"No IRS limit data found for {year} or earlier.")
    return max(valid)


def _conversion_for_year(year: int, conversions: pd.DataFrame) -> float:
    """Total planned Roth conversion for a given year, or 0 if none."""
    if conversions.empty or "Year" not in conversions.columns:
        return 0.0
    return float(conversions.loc[conversions["Year"] == year, "Conversion Amount"].sum())
