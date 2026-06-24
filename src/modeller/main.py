from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import load
from .model import project
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
        choices=["balance", "contributions", "tax", "all"],
        default="all",
        help="Which chart to show (default: all)",
    )
    args = parser.parse_args()

    for path in args.files:
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)

    scenarios = {}
    for path in args.files:
        name = path.stem.replace("_", " ").replace("-", " ").title()
        print(f"Loading {path} ...")
        data = load(path)
        results = project(data)
        scenarios[name] = (results, data["profile"])
        _print_summary(name, results, data["profile"])

    if len(scenarios) == 1:
        results, profile = next(iter(scenarios.values()))
        if args.chart == "balance":
            charts.balance_over_time(results, profile).show()
        elif args.chart == "contributions":
            charts.contributions_per_year(results).show()
        elif args.chart == "tax":
            charts.tax_over_time(results).show()
        else:
            charts.dashboard(results, profile).show()
    else:
        if args.chart == "balance":
            charts.compare_balances(scenarios).show()
        elif args.chart == "contributions":
            charts.compare_contributions(scenarios).show()
        elif args.chart == "tax":
            charts.compare_taxes(scenarios).show()
        else:
            charts.compare_dashboard(scenarios).show()


def _print_summary(name: str, results, profile) -> None:
    first = results.iloc[0]
    last = results.iloc[-1]

    print()
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {name}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Age               {int(first['Age'])} → {int(last['Age'])}")
    print(f"  Years projected   {len(results)}")
    print(f"  Final salary      ${last['Gross Salary']:>12,.0f}")
    print(f"  Traditional       ${last['Traditional Balance']:>12,.0f}")
    print(f"  Roth              ${last['Roth Balance']:>12,.0f}")
    print(f"  Total (nominal)   ${last['Total Balance']:>12,.0f}")
    if profile.account_for_inflation:
        print(f"  Total (today $)   ${last['Real Total Balance']:>12,.0f}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()


if __name__ == "__main__":
    main()
