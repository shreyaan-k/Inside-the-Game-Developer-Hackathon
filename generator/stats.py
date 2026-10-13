"""Basic per-team match stats computed from an event list (used by the realism check)."""
from __future__ import annotations

from collections import Counter
from typing import Any


def team_stats(meta: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    codes = [meta["home"]["code"], meta["away"]["code"]]
    s: dict[str, Counter] = {c: Counter() for c in codes}
    for e in events:
        team, etype, out = e["team"], e["type"], e.get("outcome")
        if team is None:
            continue
        c = s[team]
        if etype == "pass":
            c["passes"] += 1
            c["passes_complete"] += out == "complete"
        elif etype == "shot":
            c["shots"] += 1
            c["on_target"] += out in ("goal", "saved")
            c["xg"] += e["xg"]
        elif etype == "goal":
            c["goals"] += 1
        elif etype == "foul":
            c["fouls"] += 1
        elif etype == "card":
            c["yellow" if out == "yellow" else "red"] += 1
        elif etype == "tackle":
            c["tackles"] += 1
            c["tackles_won"] += out == "won"
        elif etype == "interception":
            c["interceptions"] += 1
        elif etype == "restart" and e["details"]["kind"] == "corner":
            c["corners"] += 1
        elif etype == "substitution":
            c["subs"] += 1

    total_passes = sum(s[c]["passes"] for c in codes) or 1
    result: dict[str, dict[str, float]] = {}
    for c in codes:
        d = dict(s[c])
        d["pass_accuracy"] = d.get("passes_complete", 0) / max(1, d.get("passes", 0))
        d["possession"] = d.get("passes", 0) / total_passes  # pass-share proxy
        d["xg"] = round(d.get("xg", 0.0), 2)
        result[c] = d
    return result
