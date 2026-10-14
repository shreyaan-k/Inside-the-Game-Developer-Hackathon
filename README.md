# Why? — Explainable Match Intelligence

> A live football match companion. Synthetic match events go in; six AI agents explain **why** each moment matters and **what it means next**, personalized for every viewer, in their language.

Built for the Microsoft Premier League Hackathon (Oct 2026).

**Live demo:** TODO_DEMO_URL
**Demo video (under 2 min):** TODO_YOUTUBE_URL

> All clubs, players and matches in this project are fictional and synthetic. No real match data, names or logos are used.

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Agents](#agents)
- [Microsoft technologies used](#microsoft-technologies-used)
- [Synthetic data](#synthetic-data)
- [Match intelligence](#match-intelligence)
- [Viewer modes](#viewer-modes)
- [MCP server](#mcp-server)
- [Getting started](#getting-started)
- [Deploying to Azure](#deploying-to-azure)
- [Repo layout](#repo-layout)
- [How we built it](#how-we-built-it)
- [Testing for judges](#testing-for-judges)
- [Team](#team)
- [License](#license)

---

## What it does

TODO: 3–4 sentences. Problem (scores don't explain the game) → what Why? does → who it's for (casual fans, analysts, broadcasters).

- **Ingest** synthetic match events live (passes, shots, tackles, pressure, possession changes)
- **Interpret** them into stats, player and unit ratings, tactics and chemistry
- **Explain** why each moment matters and how it may change the rest of the game
- **Render** timed overlay cues and a live match screen
- **Personalize** for five viewer modes and six languages, with voice

TODO: screenshot of the main screen → `docs/img/screen.png`

---

## Architecture

![Azure architecture](docs/img/architecture-azure.png)

![One goal, step by step](docs/img/sequence-goal.png)

TODO: 2–3 sentences on the event-driven flow: Event Hubs → Stats agent → agents on Agent Framework → screen. Adaptive refresh rate (2 Hz calm, 25 Hz big moments) with a 10-second replay buffer.

---

## Agents

| Agent | Job | Runs on |
| --- | --- | --- |
| Stats | Raw events → match state, ratings, chemistry, win chances | Code |
| Moment spotter | Flags moments and side insights, sets refresh rate | Rules + small model |
| Explainer | Writes the Why and what it means next | Large model |
| Fact-checker | Checks every claim against match state, rejects and retries | Code + small model |
| Personalizer | One version per viewer mode and language | Large model |
| Producer | Timed overlay cues, voice, full-time recap | Rules + large model |

TODO: handoff message format, retry and fallback behavior (link to `docs/agents.md`).

---

## Microsoft technologies used

| Technology | Used for |
| --- | --- |
| Microsoft Foundry | Models for all AI agents |
| Microsoft Agent Framework | Agent orchestration and handoffs |
| MCP (Azure MCP pattern) | Match, player, club and chemistry tools for agents |
| Azure Event Hubs | Live event stream |
| Azure Container Apps | Agents, Stats agent, MCP server |
| Azure Cosmos DB | Match state, players, clubs, player pairs |
| Microsoft Fabric | Season dataset and realism report |
| Azure AI Speech | Voice commentary in each language |
| Azure AI Content Safety | Screening every line before it airs |
| Azure Static Web Apps | Match screen |
| Azure Key Vault, Application Insights | Secrets, tracing every agent handoff |
| GitHub Copilot Agent Mode | TODO: what we built with it |

---

## Synthetic data

TODO: short description of the match generator.

- Event format: `docs/schema.md`
- Team styles, player traits, formations, tactics, match stakes
- Tracking frames: every player, the ball and 3 officials, once per second (`frames.json1`)
- Seeded, repeatable matches + scenario controls (red card, comeback, injury)
- Fictional league: TODO clubs × TODO players, with portfolios and history

### Realism report

| Check | Target | Ours | Pass |
| --- | --- | --- | --- |
| Goals per match | 2.0–3.5 | 2.7 | ✅ |
| Shots per team | 9–16 | 11.8 | ✅ |
| Shots on target per team | 3–6 | 4.0 | ✅ |
| xG per shot | 0.08–0.13 | 0.115 | ✅ |
| Passes per team | 350–600 | 545 | ✅ |
| Pass accuracy | 75–88% | 80.6% | ✅ |
| Possession of dominant side | 50–65% | 52.3% | ✅ |
| Fouls per match | 18–26 | 23.7 | ✅ |
| Cards per match | 2–5 | 4.5 | ✅ |
| Corners per team | 3.5–6.5 | 4.3 | ✅ |
| Ball in play | 50–62 min | 54.0 min | ✅ |
| Distance per outfield player | 9–12 km | 10.8 km | ✅ |
| Time spent sprinting (>25 km/h) | 1–5% | 3.1% | ✅ |


TODO: cite source for target ranges.

---

## Match intelligence

- Player match ratings (1.0–10.0) with logged reasons
- Unit ratings: attack, midfield, defense, with imbalance alerts
- Tactics and formations: plan vs what actually happens on the pitch
- Chemistry network between players
- Match stakes: league, cup, derby, must-win
- What it means next: win chances, likely tactical reaction, prediction check
- Rolling 2-minute event window for the AI, full log kept for stats

TODO: one example Why? card, before and after personalization.

---

## Viewer modes

| Mode | For |
| --- | --- |
| Casual | New fans |
| Analyst | Data fans |
| Club fan | Follows one club |
| Player cam | Follows one player all match |
| One metric | Tracks a single stat |

Languages: English, Spanish, Portuguese, French, Arabic, Hindi.

---

## MCP server

| Tool | Returns |
| --- | --- |
| `get_match_state(minute)` | Score, possession, momentum |
| `get_events(from_t, to_t, player?)` | Events in a window |
| `get_player(player_id, match_id)` | Player stats this match |
| `get_player_events(player_id, from_t, to_t)` | One player's events |
| `get_player_season(player_id)` | Season context |
| `get_club(club_id)` | Club profile and tactics |
| `get_chemistry(player_a, player_b)` | Pair chemistry |
| `get_top_pairs(club)` | Best partnerships |
| `post_moment(card)`, `post_handoff(message)` | Write back to state |

TODO: how to connect your own MCP client.

---

## Getting started

### Prerequisites

- TODO: Python version, Node version
- Azure subscription with a Foundry project
- TODO: other tools

### Run locally

```bash
git clone https://github.com/TODO/TODO.git
cd TODO
cp .env.example .env   # fill in keys
# TODO: install + run commands
```

### Environment variables

| Variable | What |
| --- | --- |
| TODO | TODO |

---

## Deploying to Azure

TODO: Bicep deploy steps from `/infra`.

---

## Repo layout

```
/generator     match simulator, team styles, tactics, stakes, realism report
/agents        stats, spotter, explainer, checker, personalizer, producer
/mcp-server    match-state, player, club and chemistry tools
/web           screen: pitch, cards, viewer modes
/infra         Azure deployment (Bicep)
/docs          architecture diagrams, schema, AI output formats, README assets
/examples      sample Why? card and overlay cues for building the frontend
```

---

## How we built it

TODO: tools used (Claude, GitHub Copilot Agent Mode), challenges, what we learned.

---

## Testing for judges

1. Open TODO_DEMO_URL (no login needed)
2. Press **Start match** (seed TODO)
3. Wait for the first goal, open its **Why?** card
4. Switch viewer and language from the top bar
5. Open the agent log to see the fact-checker at work

---

## Team

| Name | Role |
| --- | --- |
| TODO | TODO |

---

## License

TODO: MIT
