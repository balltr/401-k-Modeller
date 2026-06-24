from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import load
from .model import project, project_retirement
from . import charts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project 401(k) balances from one or more contribution spreadsheets."
    )
    parser.add_argument(
        "files",
        type=Path,
        nargs="+",
        help="One or more Excel workbooks. Pass multiple files to compare scenarios.",
    )
    parser.add_argument(
        "--chart",
        choices=["balance", "contributions", "tax", "retirement", "all"],
        default="all",
        help="Which chart to show (default: all)",
    )
    args = parser.parse_args()

    for path in args.files:
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)

    # scenarios: {name: (accumulation_df, retirement_df, profile)}
    scenarios = {}
    for path in args.files:
        name = path.stem.replace("_", " ").replace("-", " ").title()
        print(f"Loading {path} ...")
        data = load(path)
        accum = project(data)
        retire = project_retirement(accum, data)
        scenarios[name] = (accum, retire, data["profile"])
        _print_summary(name, accum, retire, data["profile"])

    if len(scenarios) == 1:
        accum, retire, profile = next(iter(scenarios.values()))
        if args.chart == "balance":
            charts.balance_over_time(accum, profile).show()
        elif args.chart == "contributions":
            charts.contributions_per_year(accum).show()
        elif args.chart == "tax":
            charts.tax_over_time(accum).show()
        elif args.chart == "retirement":
            charts.retirement_dashboard(accum, retire, profile).show()
        else:
            charts.dashboard(accum, profile).show()
            charts.retirement_dashboard(accum, retire, profile).show()
    else:
        if args.chart == "balance":
            charts.compare_balances(scenarios).show()
        elif args.chart == "contributions":
            charts.compare_contributions(scenarios).show()
        elif args.chart == "tax":
            charts.compare_taxes(scenarios).show()
        elif args.chart == "retirement":
            charts.compare_net_withdrawal(scenarios).show()
            charts.compare_retirement_balances(scenarios).show()
        else:
            charts.compare_dashboard(scenarios).show()


def _print_summary(name: str, accum, retire, profile) -> None:
    a_last = accum.iloc[-1]
    r_last = retire.iloc[-1] if not retire.empty else None

    print()
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {name}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  [Accumulation]")
    print(f"  Age               {int(accum.iloc[0]['Age'])} → {int(a_last['Age'])}")
    print(f"  Final salary      ${a_last['Gross Salary']:>12,.0f}")
    print(f"  Traditional       ${a_last['Traditional Balance']:>12,.0f}")
    print(f"  Roth              ${a_last['Roth Balance']:>12,.0f}")
    print(f"  Total (nominal)   ${a_last['Total Balance']:>12,.0f}")
    if profile.account_for_inflation:
        print(f"  Total (today $)   ${a_last['Real Total Balance']:>12,.0f}")
    if r_last is not None:
        print()
        print(f"  [Retirement — through age {profile.end_age}]")
        print(f"  Remaining balance ${r_last['Total Balance']:>12,.0f}")
        net = retire["Net Withdrawal"]
        print(f"  Avg net/year      ${net.mean():>12,.0f}")
        print(f"  Min net/year      ${net.min():>12,.0f}")
        print(f"  Max net/year      ${net.max():>12,.0f}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()


if __name__ == "__main__":
    main()
