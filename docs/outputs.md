# AI output formats v1.0 (locked)

What the agents produce and the web app reads. Lock these so frontend and backend can build at the same time: the frontend builds against the files in `examples/` before the agents exist.

Two formats:

| Format | Made by | Used for |
| --- | --- | --- |
| **Why? card** | Explainer → Fact-checker → Personalizer | Moments feed, side insights, "what happened here" panel, recap |
| **Overlay cue** | Producer | Timed graphics on the pitch or a broadcast feed: name tags, speed tags, lower thirds |

Both are JSON. Times use the same match clock `t` (seconds since kickoff) as events and frames, so the screen can line everything up when rewinding.

## Why? card

One card per moment **per viewer mode and language**. The same moment for a casual fan in Spanish and an analyst in English is two cards with the same `moment_id`.

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `card_id` | string | `c-m-RVR-HBR-42-0412-casual-en` | Unique |
| `moment_id` | string | `m-RVR-HBR-42-0412` | Same for every version of one moment |
| `match_id` | string | `m-RVR-HBR-42` | |
| `t` | float | 1272.8 | When the moment happened |
| `minute`, `added` | int | 22, 0 | For display, same as events |
| `kind` | string | `goal` | goal, big_chance, save, card, momentum_swing, tactical_shift, milestone, chemistry, unit_imbalance, recap |
| `priority` | string | `main` | `main` = moments feed, `side` = quiet side insight |
| `importance` | float | 0.92 | 0–1, from the Moment spotter |
| `team` | string or null | `RVR` | Club the moment is about |
| `player_ids` | list | `["RVR-09", "RVR-07"]` | Players involved, main one first |
| `event_ids` | list | `["m-RVR-HBR-42-00581"]` | Events behind the moment, for highlighting and replay |
| `window` | object | `{"from_t": 1252.8, "to_t": 1274.3}` | Stretch to replay or highlight |
| `viewer` | object | see below | Who this version is for |
| `headline` | string | `Goal! Quinberg puts Riverton ahead` | Short, one line |
| `why` | string | | Why it mattered. 1–3 sentences |
| `next` | object or null | see below | What it means for the rest of the game |
| `facts` | list | see below | Every claim the text makes, with its source number |
| `fact_check` | object | `{"status": "approved", "attempts": 2}` | `approved` or `fallback` (plain stat card) |
| `audio_url` | string or null | | Azure AI Speech audio for this card |

**`viewer`**: `{"mode": "casual", "lang": "en", "club": null, "player_id": null, "metric": null}`
- `mode`: casual, analyst, club_fan, player_cam, one_metric
- `lang`: en, es, pt, fr, ar, hi
- `club`, `player_id`, `metric`: set for club_fan, player_cam and one_metric

**`next`**: `{"text": "...", "win_prob_before": {"RVR": 0.41, "draw": 0.31, "HBR": 0.28}, "win_prob_after": {"RVR": 0.63, "draw": 0.22, "HBR": 0.15}, "prediction": "HBR push full-backs forward", "check_after_t": 1872.8}`
- `prediction` and `check_after_t`: the prediction check later reports whether it came true

**`facts`**: `[{"claim": "Quinberg's 3rd shot of the match", "value": 3, "source": "player_match.shots"}]`
- The Fact-checker approves the card only if every `value` matches match state

## Overlay cue

A timed instruction to show one graphic. Many cues can come from one card.

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `cue_id` | string | `q-m-RVR-HBR-42-0412-lt-casual-en` | Unique |
| `card_id` | string or null | `c-m-RVR-HBR-42-0412-casual-en` | The card it came from, if any |
| `match_id` | string | `m-RVR-HBR-42` | |
| `start_t` | float | 1274.0 | When to show it |
| `duration_s` | float | 8 | How long to show it |
| `slot` | string | `lower_third` | lower_third, player_tag, top_bar, side_panel, full_screen |
| `template` | string | `why` | name_tag, speed_tag, distance_tag, shot_speed, goal, why, stat_compare, recap |
| `priority` | int | 1 | 1 = highest. A new cue replaces a lower-priority one in the same slot |
| `viewer` | object | | Same shape as on the card |
| `anchor` | object or null | `{"player_id": "RVR-09"}` | For tags that follow a player on the pitch |
| `text` | string | | Text to show |
| `data` | object | `{"speed_kmh": 31.4}` | Numbers the template draws |
| `voice` | object or null | `{"audio_url": "...", "offset_s": 0.5}` | Play with the cue |

## Rules

- Times are match clock seconds, never wall-clock time.
- IDs link everything: cue → card → events and frames.
- Text is already personalized and translated. The frontend never rewrites it.
- Player names come from `meta.json` (lookup by `player_id`). Cards may also include names in text.
- A card with `fact_check.status: "fallback"` has no AI text: show `headline` plus the numbers in `facts`.

See `examples/why_card.json` and `examples/overlay_cue.json`.
