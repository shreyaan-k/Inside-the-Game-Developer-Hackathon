"""Realism check: generate many matches and compare averages to typical league ranges.

Run:  python -m generator.realism --matches 200

The target ranges are rough working targets for top-flight football. Confirm each one
against a public source before quoting them (see README).
"""
from __future__ import annotations

import argparse
import itertools
import statistics as st
import sys

from .rosters import CLUBS
from .schema import validate_match
from .sim import simulate_match
from .stats import team_stats

# name -> (low, high, unit)
TARGETS = {
    "Goals per match": (2.0, 3.5, ""),
    "Shots per team": (9.0, 16.0, ""),
    "Shots on target per team": (3.0, 6.0, ""),
    "xG per shot": (0.08, 0.13, ""),
    "Passes per team": (350.0, 600.0, ""),
    "Pass accuracy": (75.0, 88.0, "%"),
    "Possession of dominant side": (50.0, 65.0, "%"),
    "Fouls per match": (18.0, 26.0, ""),
    "Cards per match": (2.0, 5.0, ""),
    "Corners per team": (3.5, 6.5, ""),
    "Ball in play": (50.0, 62.0, " min"),
}


def run(n_matches: int, base_seed: int = 1000) -> tuple[dict[str, float], int]:
    pairs = list(itertools.permutations(sorted(CLUBS), 2))
    rows: dict[str, list[float]] = {k: [] for k in TARGETS}
    invalid = 0
    for i in range(n_matches):
        home, away = pairs[i % len(pairs)]
        meta, events = simulate_match(home, away, base_seed + i)
        if validate_match(meta, events):
            invalid += 1
        s = team_stats(meta, events)
        teams = list(s.values())
        shots = sum(t.get("shots", 0) for t in teams)
        rows["Goals per match"].append(meta["result"]["home"] + meta["result"]["away"])
        rows["Fouls per match"].append(sum(t.get("fouls", 0) for t in teams))
        rows["Cards per match"].append(sum(t.get("yellow", 0) + t.get("red", 0) for t in teams))
        rows["Possession of dominant side"].append(100 * max(t["possession"] for t in teams))
        rows["Ball in play"].append(meta["duration"]["ball_in_play_s"] / 60)
        if shots:
            rows["xG per shot"].append(sum(t["xg"] for t in teams) / shots)
        for t in teams:
            rows["Shots per team"].append(t.get("shots", 0))
            rows["Shots on target per team"].append(t.get("on_target", 0))
            rows["Passes per team"].append(t.get("passes", 0))
            rows["Pass accuracy"].append(100 * t["pass_accuracy"])
            rows["Corners per team"].append(t.get("corners", 0))
    return {k: st.mean(v) for k, v in rows.items()}, invalid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--matches", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1000)
    args = ap.parse_args(argv)

    means, invalid = run(args.matches, args.seed)
    print(f"Realism report: {args.matches} matches, {invalid} failed schema validation\n")
    print(f"{'Check':30} {'Target':>14} {'Ours':>9}  Pass")
    passed = 0
    for name, (lo, hi, unit) in TARGETS.items():
        v = means[name]
        ok = lo <= v <= hi
        passed += ok
        fmt = (lambda x: f"{x:.3f}") if hi < 1 else (lambda x: f"{x:.1f}")
        print(f"{name:30} {fmt(lo) + '-' + fmt(hi) + unit:>14} {fmt(v) + unit:>9}  {'yes' if ok else 'NO'}")
    print(f"\n{passed}/{len(TARGETS)} checks pass")
    return 0 if passed == len(TARGETS) and invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
