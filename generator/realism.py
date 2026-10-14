"""Realism check: generate many matches and compare averages to typical league ranges.

Run:  python -m generator.realism --matches 200

The target ranges are rough working targets for top-flight football. Confirm each one
against a public source before quoting them (see README).
"""
from __future__ import annotations

import argparse
import itertools
import math
import statistics as st
import sys

from .rosters import CLUBS
from .schema import validate_match, validate_frames
from .sim import simulate_match_full
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
    "Distance per outfield player": (9.0, 12.0, " km"),
    "Time spent sprinting (>25 km/h)": (1.0, 5.0, "%"),
}

def _movement(meta: dict, frames: list[dict]) -> tuple[list[float], float]:
    """Distance (km) of outfield players who played the whole match, and % of time sprinting."""
    gks = {p["player_id"] for side in ("home", "away")
           for p in meta[side]["lineup"] + meta[side]["bench"] if p["position"] == "GK"}
    dist: dict[str, float] = {}
    seen: dict[str, int] = {}
    prev: dict[str, tuple[float, float, int]] = {}
    sprint = total = 0
    for f in frames:
        for pid, (x, y, kmh) in f["players"].items():
            if pid in gks:
                continue
            seen[pid] = seen.get(pid, 0) + 1
            total += 1
            sprint += kmh > 25
            if pid in prev and prev[pid][2] == f["period"]:
                dist[pid] = dist.get(pid, 0.0) + math.dist((x, y), prev[pid][:2])
            prev[pid] = (x, y, f["period"])
    full = [d / 1000 for pid, d in dist.items() if seen[pid] >= 0.95 * len(frames)]
    return full, 100 * sprint / max(total, 1)



def run(n_matches: int, base_seed: int = 1000) -> tuple[dict[str, float], int]:
    pairs = list(itertools.permutations(sorted(CLUBS), 2))
    rows: dict[str, list[float]] = {k: [] for k in TARGETS}
    invalid = 0
    for i in range(n_matches):
        home, away = pairs[i % len(pairs)]
        meta, events = simulate_match(home, away, base_seed + i)
        if validate_match(meta, events) or validate_frames(meta, frames):
            invalid += 1
        km, sprint_pct = _movement(meta, frames)
        rows["Distance per outfield player"].extend(km)
        rows["Time spent sprinting (>25 km/h)"].append(sprint_pct)
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
    ap.add_argument("--matches", type=int, default=100)
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
