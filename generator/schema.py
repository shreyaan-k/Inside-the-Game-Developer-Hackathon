"""Event format v1.0: the locked contract between the generator and everything downstream.

Every event is one flat JSON object (one line in a .jsonl file). Coordinates are
absolute pitch metres: x runs 0 -> 105 along the length, y runs 0 -> 68 across the
width. Which goal each team attacks in each period is recorded in the match metadata.

See docs/schema.md for the human-readable version of this file.
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1.0"

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0

# type -> allowed outcomes (None means the event has no outcome)
EVENT_TYPES: dict[str, set[str | None]] = {
     "half_start": {None},
     "half_end": {None},
     "restart": {None}, #  details.kind: kickoff, throw_in, goal_kick, corner, free_kick, penalty
     "pass": {"complete", "incomplete"},
     "carry": {"complete"},
     "pressure": {None},
     "tackle": {"won", "lost"},
     "interception": {"won"},
     "clearance": {None},
     "block": {None},
     "foul": {"committed"},
     "card": {"yellow", "second_yellow", "red"},
     "shot": {"goal", "saved", "blocked", "off_target"},
     "save": {"held", "parried"},
     "goal": {None},
     "ball_out": {None},
     "possession_change": {None},
     "substitution": {None},
 }
 
#  Events that happen at a point on the pitch carry x/y.
LOCATED_TYPES = set(EVENT_TYPES) - {"half_start", "half_end", "substitution", "possession_change"}
#  Events with a start and end point.
MOVING_TYPES = {"pass", "carry", "shot"}
#  Events that belong to no team.
TEAMLESS_TYPES = {"half_start", "half_end"}
 
RESTART_KINDS = {"kickoff", "throw_in", "goal_kick", "corner", "free_kick", "penalty"}
 
REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
     "event_id": str,
     "match_id": str,
     "seq": int,
     "t": (int, float),
     "period": int,
     "minute": int,
     "added": int,
     "second": int,
     "type": str,
     "team": (str, type(None)),
     "player_id": (str, type(None)),
     "possession_id": int,
     "possession_team": (str, type(None)),
 }
 
OPTIONAL_FIELDS: dict[str, type | tuple[type, ...]] = {
     "x": (int, float),
     "y": (int, float),
     "end_x": (int, float),
     "end_y": (int, float),
     "outcome": str,
     "related_player_id": str,
     "speed_kmh": (int, float),
     "under_pressure": bool,
     "xg": (int, float),
     "details": dict,
 }
 
ALL_FIELDS = set(REQUIRED_FIELDS) | set(OPTIONAL_FIELDS)
 
 
def _in_pitch(x: float, y: float) -> bool:
     return -0.01 <= x <= PITCH_LENGTH + 0.01 and -0.01 <= y <= PITCH_WIDTH + 0.01
 
 
def validate_event(e: dict[str, Any]) -> list[str]:
     """Return a list of problems with one event. Empty list means valid."""
     errs: list[str] = []
     eid = e.get("event_id", "?")
 
     for name, typ in REQUIRED_FIELDS.items():
         if name not in e:
             errs.append(f"{eid}: missing {name}")
         elif not isinstance(e[name], typ) or isinstance(e[name], bool) and typ is not bool:
             errs.append(f"{eid}: {name} has wrong type {type(e[name]).__name__}")
     for name, typ in OPTIONAL_FIELDS.items():
         if name in e and not isinstance(e[name], typ):
             errs.append(f"{eid}: {name} has wrong type {type(e[name]).__name__}")
     unknown = set(e) - ALL_FIELDS
     if unknown:
         errs.append(f"{eid}: unknown fields {sorted(unknown)}")
     if errs:
         return errs
 
     etype = e["type"]
     if etype not in EVENT_TYPES:
         return [f"{eid}: unknown type {etype}"]
     if e.get("outcome") not in EVENT_TYPES[etype]:
         errs.append(f"{eid}: outcome {e.get('outcome')!r} not allowed for {etype}")
 
     if e["period"] not in (1, 2):
         errs.append(f"{eid}: period must be 1 or 2")
     if not 0 <= e["second"] <= 59:
         errs.append(f"{eid}: second out of range")
     if e["added"] < 0:
         errs.append(f"{eid}: added must be >= 0")
 
     if etype in TEAMLESS_TYPES:
         if e["team"] is not None:
             errs.append(f"{eid}: {etype} must have team null")
     elif e["team"] is None:
         errs.append(f"{eid}: {etype} needs a team")
 
     if etype in LOCATED_TYPES:
         if "x" not in e or "y" not in e:
             errs.append(f"{eid}: {etype} needs x and y")
         elif not _in_pitch(e["x"], e["y"]):
             errs.append(f"{eid}: x/y off the pitch ({e['x']}, {e['y']})")
     if etype in MOVING_TYPES:
         if "end_x" not in e or "end_y" not in e:
             errs.append(f"{eid}: {etype} needs end_x and end_y")
         elif not _in_pitch(e["end_x"], e["end_y"]):
             errs.append(f"{eid}: end point off the pitch ({e['end_x']}, {e['end_y']})")

     if etype == "shot":
        if "xg" not in e or not 0 <= e["xg"] <= 1:
            errs.append(f"{eid}: shot needs xg in [0, 1]")
        if "speed_kmh" not in e:
            errs.append(f"{eid}: shot needs speed_kmh")
     if etype == "pass" and "speed_kmh" not in e:
        errs.append(f"{eid}: pass needs speed_kmh")
     if etype == "restart" and e.get("details", {}).get("kind") not in RESTART_KINDS:
        errs.append(f"{eid}: restart needs details.kind in {sorted(RESTART_KINDS)}")
     if etype == "substitution" and "related_player_id" not in e:
        errs.append(f"{eid}: substitution needs related_player_id (player coming on)")
     if etype in {"pass", "carry", "shot", "tackle", "interception", "clearance", "block", "foul",
                 "card", "save", "goal", "pressure", "substitution"} and e["player_id"] is None:
        errs.append(f"{eid}: {etype} needs player_id")
     return errs


def validate_match(meta: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    """Check a whole match: every event valid, plus cross-event consistency."""
    errs: list[str] = []
    home, away = meta["home"]["code"], meta["away"]["code"]
    squad: dict[str, set[str]] = {
        home: {p["player_id"] for p in meta["home"]["lineup"] + meta["home"]["bench"]},
        away: {p["player_id"] for p in meta["away"]["lineup"] + meta["away"]["bench"]},
    }

    last_t, last_seq, last_pos = -1.0, -1, -1
    goals = {home: 0, away: 0}
    for e in events:
        errs.extend(validate_event(e))
        if e.get("match_id") != meta["match_id"]:
            errs.append(f"{e.get('event_id')}: wrong match_id")
        if e["t"] < last_t:
            errs.append(f"{e['event_id']}: t goes backwards")
        if e["seq"] <= last_seq:
            errs.append(f"{e['event_id']}: seq not increasing")
        if e["possession_id"] < last_pos:
            errs.append(f"{e['event_id']}: possession_id goes backwards")
        last_t, last_seq, last_pos = e["t"], e["seq"], e["possession_id"]

        team = e["team"]
        if team is not None and team not in squad:
            errs.append(f"{e['event_id']}: unknown team {team}")
        if team in squad and e["player_id"] is not None and e["player_id"] not in squad[team]:
            errs.append(f"{e['event_id']}: player {e['player_id']} not in {team} squad")
        if e["type"] == "goal":
            goals[team] += 1

    if goals[home] != meta["result"]["home"] or goals[away] != meta["result"]["away"]:
        errs.append(f"goal events {goals} do not match result {meta['result']}")
    return errs
