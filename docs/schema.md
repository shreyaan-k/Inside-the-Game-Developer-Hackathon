# Event format v1.0 (locked)

The contract between the match generator and everything downstream (Stats agent, MCP server, screen). The code version lives in `generator/schema.py`, and `validate_match()` checks every generated match against it.

Change this format only by bumping `schema_version` and updating both files.

## Files

Each match is written as two files in `data/matches/<match_id>/`:

| File | What |
| --- | --- |
| `meta.json` | Match metadata: clubs, lineups, bench, result, durations |
| `events.jsonl` | One event per line, in order |

When streamed (`--stream`), the first line is the metadata with `"type": "match_meta"`, then one event per line.

## Pitch and coordinates

- Pitch is **105 × 68 metres**.
- `x` runs 0 → 105 along the length, `y` runs 0 → 68 across the width.
- Coordinates are **absolute**: they don't flip with possession.
- `meta.attacking_right` says which club attacks toward x = 105 in each period. Teams switch ends at halftime.

## Event fields

Every event has these fields:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `event_id` | string | `m-RVR-HBR-42-00581` | Unique, sortable |
| `match_id` | string | `m-RVR-HBR-42` | |
| `seq` | int | 581 | 0, 1, 2… in order |
| `t` | float | 1272.8 | Seconds of match clock since kickoff, halftime excluded. Always increasing |
| `period` | int | 1 | 1 or 2 |
| `minute` | int | 22 | Football minute as shown on screen (1–45, 46–90) |
| `added` | int | 0 | Stoppage minute, e.g. `minute 45, added 2` = 45+2 |
| `second` | int | 12 | 0–59 |
| `type` | string | `goal` | See event types |
| `team` | string or null | `RVR` | Club that did it. Null only for half start/end |
| `player_id` | string or null | `RVR-09` | Player who did it |
| `possession_id` | int | 63 | Increments every time possession changes |
| `possession_team` | string or null | `RVR` | Club in possession at that moment |

Optional fields, present when relevant:

| Field | Type | Used by |
| --- | --- | --- |
| `x`, `y` | float | Every on-pitch event |
| `end_x`, `end_y` | float | `pass`, `carry`, `shot` |
| `outcome` | string | See table below |
| `related_player_id` | string | Pass receiver, player tackled or fouled, assister on a goal, player coming on in a sub |
| `speed_kmh` | float | Ball speed (pass, shot), carry speed |
| `under_pressure` | bool | `pass`, `carry`, `shot` |
| `xg` | float | `shot` (0–1) |
| `details` | object | Type-specific extras, listed below |

## Event types

| Type | Outcomes | Notes and `details` |
| --- | --- | --- |
| `half_start`, `half_end` | none | No team |
| `restart` | none | `kind`: kickoff, throw_in, goal_kick, corner, free_kick, penalty |
| `pass` | complete, incomplete | `length_m`; `set_piece`, `long_ball`, `cross` when true |
| `carry` | complete | `length_m`; `beat_player` when the carrier got past a tackle |
| `pressure` | none | Defender closing down the ball carrier |
| `tackle` | won, lost | `related_player_id` = carrier |
| `interception` | won | Ball won from an opponent's failed pass |
| `clearance` | none | Defender clears a cross |
| `block` | none | Defender blocks a shot |
| `foul` | committed | `related_player_id` = player fouled |
| `card` | yellow, second_yellow, red | second_yellow and red send the player off |
| `shot` | goal, saved, blocked, off_target | `xg`, `speed_kmh`, `distance_m`; `body_part`, `set_piece` |
| `save` | held, parried | Goalkeeper |
| `goal` | none | `related_player_id` = assister if any; `score` after the goal |
| `ball_out` | none | `next`: throw_in, goal_kick or corner; `deflected` when true |
| `possession_change` | none | `team` = club that gains the ball; `reason` |
| `substitution` | none | `player_id` off, `related_player_id` on; `position` |

## Match metadata (`meta.json`)

| Field | What |
| --- | --- |
| `schema_version`, `generator` | Format and generator versions |
| `match_id`, `seed` | Same seed and clubs = same match |
| `competition` | League, season, matchday |
| `venue` | Home stadium |
| `home`, `away` | Club info, formation, `lineup` and `bench` (player id, name, number, position) |
| `attacking_right` | Club attacking x = 105 in period 1 and 2 |
| `first_kickoff` | Club that kicked off the match |
| `result` | Final score |
| `duration` | Length of each period and ball-in-play seconds |
| `event_count` | Number of events |

## Example

```json
{"event_id": "m-RVR-HBR-42-00581", "match_id": "m-RVR-HBR-42", "seq": 581, "t": 1272.8,
 "period": 1, "minute": 22, "added": 0, "second": 12, "type": "goal", "team": "RVR",
 "player_id": "RVR-09", "possession_id": 63, "possession_team": "RVR", "x": 97.6, "y": 33.5,
 "related_player_id": "RVR-07", "details": {"score": {"RVR": 1, "HBR": 0}}}
```