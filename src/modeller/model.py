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

        # Employee contributions
        target_take_home = c.get("Target Net Take-Home ($)", float("nan"))
        if not math.isnan(target_take_home):
            # Solve for the contribution amount that achieves the target take-home.
            # Traditional lowers taxable income so we need a binary search.
            # Roth doesn't affect taxes so it's direct algebra.
            if trad_pct > 0 and roth_pct == 0:
                trad_contrib = _solve_trad_contrib(
                    salary, target_take_home, year, filing_status,
                    brackets, profile.state_tax_working, irs_limit,
                )
                roth_contrib = 0.0
            elif roth_pct > 0 and trad_pct == 0:
                tax_full = tax_module.calculate_tax(
                    salary, year, filing_status, brackets, profile.state_tax_working
                )
                roth_contrib = max(0.0, min(salary - tax_full - target_take_home, irs_limit))
                trad_contrib = 0.0
            else:
                trad_contrib = min(salary * trad_pct, irs_limit)
                roth_contrib = min(salary * roth_pct, max(0, irs_limit - trad_contrib))
        else:
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

        net_take_home = salary - trad_contrib - roth_contrib - tax_owed

        rows.append({
            "Year": year,
            "Age": age,
            "Gross Salary": salary,
            "Traditional Contrib": trad_contrib,
            "Roth Contrib": roth_contrib,
            "Employer Match": employer_match,
            "Net Take-Home": net_take_home,
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
        target_net = float(w["Take-Home Income ($)"])
        filing_status = w["Filing Status"]
        bracket_limit = w["Traditional Bracket Limit (%)"]

        # How much Traditional can we take before crossing the bracket limit?
        trad_ceiling = tax_module.max_income_in_bracket(
            bracket_limit, year, filing_status, brackets
        )

        # Solve for the gross withdrawal that delivers target_net after taxes.
        gross_withdrawal = min(
            _solve_gross_for_net_target(
                target_net, trad_balance, trad_ceiling, roth_balance,
                year, filing_status, brackets, profile.state_tax_retirement,
            ),
            total,
        )

        trad_withdrawal, roth_withdrawal = _split_withdrawal(
            gross_withdrawal, trad_balance, trad_ceiling, roth_balance
        )

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


def _split_withdrawal(
    gross: float,
    trad_balance: float,
    trad_ceiling: float,
    roth_balance: float,
) -> tuple:
    """Apply bracket-aware Trad/Roth split. Returns (trad_withdrawal, roth_withdrawal)."""
    trad_w = min(trad_balance, trad_ceiling, gross)
    roth_w = min(roth_balance, gross - trad_w)
    still_needed = gross - trad_w - roth_w
    if still_needed > 0:
        trad_w += min(still_needed, trad_balance - trad_w)
    return trad_w, roth_w


def _solve_gross_for_net_target(
    target_net: float,
    trad_balance: float,
    trad_ceiling: float,
    roth_balance: float,
    year: int,
    filing_status: str,
    brackets,
    state_rate: float,
) -> float:
    """Binary search: find the gross withdrawal that yields target_net after tax."""
    lo, hi = 0.0, trad_balance + roth_balance
    for _ in range(60):
        mid = (lo + hi) / 2
        trad_w, roth_w = _split_withdrawal(mid, trad_balance, trad_ceiling, roth_balance)
        net = trad_w + roth_w - tax_module.calculate_tax(trad_w, year, filing_status, brackets, state_rate)
        if net < target_net:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _solve_trad_contrib(
    salary: float,
    target_take_home: float,
    year: int,
    filing_status: str,
    brackets,
    state_rate: float,
    irs_limit: float,
) -> float:
    """Binary search for the Traditional contribution that hits target_take_home.

    Traditional contributions reduce taxable income, so there's no closed-form
    solution across bracket boundaries. 60 iterations gives sub-cent precision.
    """
    lo, hi = 0.0, min(salary, irs_limit)
    for _ in range(60):
        mid = (lo + hi) / 2
        tax = tax_module.calculate_tax(salary - mid, year, filing_status, brackets, state_rate)
        if salary - mid - tax > target_take_home:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


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
