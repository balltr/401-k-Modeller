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


def project_retirement(accumulation: pd.DataFrame, data: dict) -> pd.DataFrame:
    """Model year-by-year withdrawals from retirement through profile.end_year.

    Each year the algorithm fills the lowest tax brackets with Traditional
    withdrawals first, then covers any remainder with tax-free Roth. If Roth
    runs dry, additional Traditional is taken at whatever rate applies.
    """
    profile = data["profile"]
    withdrawals = data["withdrawals"]
    brackets = data["tax_brackets"]

    last = accumulation.iloc[-1]
    trad_balance = last["Traditional Balance"]
    roth_balance = last["Roth Balance"]
    accum_start = int(accumulation.index.min())

    # Derive the end year from end_age: retirement year is the year after the
    # last accumulation year, then count forward from retirement_age to end_age.
    retirement_year = int(accumulation.index.max()) + 1
    end_year = retirement_year + (profile.end_age - profile.retirement_age)

    rows = []

    for year in withdrawals.index:
        if year > end_year:
            break

        total = trad_balance + roth_balance
        if total <= 0:
            break

        w = withdrawals.loc[year]
        target = float(w["Withdrawal ($)"])
        gross_withdrawal = min(target, total)
        filing_status = w["Filing Status"]
        bracket_limit = w["Traditional Bracket Limit (%)"]

        # How much Traditional can we take before crossing the bracket limit?
        trad_ceiling = tax_module.max_income_in_bracket(
            bracket_limit, year, filing_status, brackets
        )

        # Step 1: fill low brackets with Traditional up to the ceiling
        trad_withdrawal = min(trad_balance, trad_ceiling, gross_withdrawal)

        # Step 2: cover the remainder with Roth (tax-free)
        roth_withdrawal = min(roth_balance, gross_withdrawal - trad_withdrawal)

        # Step 3: if Roth can't cover the rest, take more Traditional at higher rates
        still_needed = gross_withdrawal - trad_withdrawal - roth_withdrawal
        if still_needed > 0:
            extra_trad = min(still_needed, trad_balance - trad_withdrawal)
            trad_withdrawal += extra_trad

        tax = tax_module.calculate_tax(
            trad_withdrawal, year, filing_status, brackets, profile.state_tax_retirement
        )
        net_withdrawal = trad_withdrawal + roth_withdrawal - tax

        # Remaining balances grow after withdrawal
        trad_balance = (trad_balance - trad_withdrawal) * (1 + profile.annual_return)
        roth_balance = (roth_balance - roth_withdrawal) * (1 + profile.annual_return)
        total_balance = trad_balance + roth_balance

        years_elapsed = year - accum_start
        real_total = total_balance / (1 + profile.inflation_rate) ** years_elapsed
        real_net = net_withdrawal / (1 + profile.inflation_rate) ** years_elapsed

        rows.append({
            "Year": year,
            "Age": int(w["Age"]) if "Age" in withdrawals.columns else None,
            "Gross Withdrawal": gross_withdrawal,
            "Traditional Withdrawal": trad_withdrawal,
            "Roth Withdrawal": roth_withdrawal,
            "Tax Owed": tax,
            "Net Withdrawal": net_withdrawal,
            "Real Net Withdrawal": real_net,
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
