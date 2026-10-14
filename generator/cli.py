"""Command line: generate a match to files, or stream it live as JSON lines.

Examples
--------
  # write data/matches/<match_id>/meta.json, events.jsonl, and frames.jsonl
  python -m generator.cli --home RVR --away HBR --seed 42

  # stream events to stdout in "real time", 30x faster than a real match
  python -m generator.cli --home RVR --away HBR --seed 42 --stream --speed 30

  # list the fictional clubs
  python -m generator.cli --clubs
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .rosters import CLUBS
from .schema import validate_match, validate_frames
from .sim import simulate_match_full
from .stats import team_stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m generator.cli",
                                 description="Generate a synthetic football match.")
    ap.add_argument("--home", default="RVR", help="home club code")
    ap.add_argument("--away", default="HBR", help="away club code")
    ap.add_argument("--seed", type=int, default=42, help="same seed = same match")
    ap.add_argument("--matchday", type=int, default=None)
    ap.add_argument("--out", type=Path, default=Path("data/matches"), help="output folder")
    ap.add_argument("--stream", action="store_true", help="print events to stdout as they happen")
    ap.add_argument("--speed", type=float, default=1.0, help="stream speed multiplier (1 = real time)")
    ap.add_argument("--clubs", action="store_true", help="list clubs and exit")
    args = ap.parse_args(argv)

    if args.clubs:
        for c in CLUBS.values():
            print(f"{c.code}  {c.name:20} {c.stadium}")
        return 0

    meta, events = simulate_match_full(args.home, args.away, args.seed, matchday=args.matchday)
    errors = validate_match(meta, events) + validate_frames(meta, frames)
    if errors:
        print(f"generated match failed validation ({len(errors)} problems):", file=sys.stderr)
        print("\n".join(errors[:20]), file=sys.stderr)
        return 1

    if args.stream:
        print(json.dumps({"type": "match_meta", **meta}), flush=True)
        stream = sorted([(e["t"], 1, e) for e in events] + 
                       [(f["t"], 0, {"type": "frame", **f}) for f in frames],
                       key=lambda item: (item[0], item,[1]))
        last_t = 0.0
        try:
            for t, _, item in stream:
                wait = (t - last_t) / max(args.speed, 0.001)
                if wait > 0:
                    time.sleep(wait)
                last_t = t
                print(json.dumps(item, ensure_ascii=False), flush=True)
        except (BrokenPipeError, KeyboardInterrupt):  # reader went away (e.g. `| head`)
            sys.stderr.close()
        return 0

    folder = args.out / meta["match_id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    with open(folder / "events.jsonl", "w", encoding="utf-8") as f:
        for fr in frames:
            f.write(json.dumps(fr, seperators=(",", ":")) + "\n")

    tats(meta, events)
    h, a = meta["home"]["code"], meta["away"]["code"]
    print(f"{meta['home']['name']} {meta['result']['home']} - {meta['result']['away']} {meta['away']['name']}"
          f"  ({len(events)} events, {len(frames)} frames)")
    for label, key, fmt in [("Shots", "shots", "{:.0f}"), ("On target", "on_target", "{:.0f}"),
                            ("xG", "xg", "{:.2f}"), ("Passes", "passes", "{:.0f}"),
                            ("Pass accuracy", "pass_accuracy", "{:.0%}"), ("Possession", "possession", "{:.0%}"),
                            ("Fouls", "fouls", "{:.0f}"), ("Corners", "corners", "{:.0f}")]:
        print(f"  {label:14} {fmt.format(s[h].get(key, 0)):>6}  {fmt.format(s[a].get(key, 0)):>6}")
    print(f"Saved to {folder}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
