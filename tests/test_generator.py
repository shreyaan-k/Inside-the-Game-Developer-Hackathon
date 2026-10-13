"""Tests for the event schema and match generator v1."""
from __future__ import annotations

import json
from collections import Counter

import pytest

from generator import simulate_match, validate_event, validate_match
from generator.rosters import CLUBS
from generator.schema import EVENT_TYPES, PITCH_LENGTH, PITCH_WIDTH

SEEDS = [1, 2, 3, 42, 777]


@pytest.fixture(scope="module")
def matches():
    return [simulate_match("RVR", "HBR", s) for s in SEEDS]


def test_every_match_passes_validation(matches):
    for meta, events in matches:
        assert validate_match(meta, events) == []


def test_same_seed_same_match():
    a = simulate_match("KST", "ASH", 99)
    b = simulate_match("KST", "ASH", 99)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_different_seed_different_match():
    a_meta, a_events = simulate_match("KST", "ASH", 99)
    b_meta, b_events = simulate_match("KST", "ASH", 100)
    assert a_events != b_events


def test_match_lasts_ninety_minutes_plus_stoppage(matches):
    for meta, events in matches:
        d = meta["duration"]
        assert 45 * 60 < d["period_1_s"] < 45 * 60 + 300
        assert 45 * 60 < d["period_2_s"] < 45 * 60 + 450
        assert events[0]["type"] == "half_start" and events[-1]["type"] == "half_end"
        assert [e["period"] for e in events if e["type"] == "half_start"] == [1, 2]


def test_core_event_types_present(matches):
    seen = Counter(e["type"] for _, events in matches for e in events)
    for etype in ("pass", "carry", "shot", "tackle", "interception", "pressure", "foul",
                  "possession_change", "restart", "substitution", "ball_out"):
        assert seen[etype] > 0, etype
    assert set(seen) <= set(EVENT_TYPES)


def test_coordinates_on_pitch(matches):
    for _, events in matches:
        for e in events:
            for kx, ky in (("x", "y"), ("end_x", "end_y")):
                if kx in e:
                    assert 0 <= e[kx] <= PITCH_LENGTH and 0 <= e[ky] <= PITCH_WIDTH


def test_teams_switch_ends_at_halftime(matches):
    """Shots attack x=105 in one half and x=0 in the other."""
    meta, events = matches[0]
    home = meta["home"]["code"]
    for period, goal_x in ((1, PITCH_LENGTH), (2, 0.0)):
        shots = [e for e in events if e["type"] == "shot" and e["team"] == home and e["period"] == period
                 and e["outcome"] != "blocked"]
        assert shots, "need home shots in each half for this check"
        for s in shots:
            assert s["end_x"] == goal_x


def test_goals_match_result_and_have_shots(matches):
    for meta, events in matches:
        goals = [e for e in events if e["type"] == "goal"]
        assert len(goals) == meta["result"]["home"] + meta["result"]["away"]
        goal_shots = [e for e in events if e["type"] == "shot" and e["outcome"] == "goal"]
        assert len(goal_shots) == len(goals)


def test_at_most_three_subs_and_bench_players_come_on(matches):
    for meta, events in matches:
        for side in ("home", "away"):
            code = meta[side]["code"]
            bench = {p["player_id"] for p in meta[side]["bench"]}
            subs = [e for e in events if e["type"] == "substitution" and e["team"] == code]
            assert len(subs) <= 3
            assert all(s["related_player_id"] in bench for s in subs)


def test_clock_fields_consistent(matches):
    _, events = matches[0]
    for e in events:
        if e["period"] == 1:
            assert 1 <= e["minute"] <= 45
        else:
            assert 46 <= e["minute"] <= 90
        if e["added"]:
            assert e["minute"] in (45, 90)


def test_validator_catches_bad_events():
    good = {"event_id": "e1", "match_id": "m", "seq": 0, "t": 1.0, "period": 1, "minute": 1,
            "added": 0, "second": 1, "type": "pass", "team": "RVR", "player_id": "RVR-09",
            "possession_id": 1, "possession_team": "RVR", "x": 50.0, "y": 30.0, "end_x": 60.0,
            "end_y": 30.0, "outcome": "complete", "speed_kmh": 40.0}
    assert validate_event(good) == []
    assert validate_event({**good, "outcome": "goal"})  # wrong outcome for a pass
    assert validate_event({**good, "x": 120.0})  # off the pitch
    assert validate_event({**good, "type": "dance"})  # unknown type
    assert validate_event({**good, "colour": "red"})  # unknown field
    bad = dict(good)
    del bad["end_x"]
    assert validate_event(bad)  # pass needs an end point


def test_all_club_pairs_simulate():
    codes = sorted(CLUBS)
    for i, home in enumerate(codes):
        away = codes[(i + 1) % len(codes)]
        meta, events = simulate_match(home, away, seed=i)
        assert validate_match(meta, events) == []


def test_same_club_twice_rejected():
    with pytest.raises(ValueError):
        simulate_match("RVR", "RVR", 1)
