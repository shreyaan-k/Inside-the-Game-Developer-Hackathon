"""Match generator v1: plays a full synthetic match, one on-ball action at a time.

How it works
------------
The simulator tracks which team has the ball, who carries it and where it is. Each step
the carrier passes, carries or shoots. Odds depend on pitch zone, pressure and player
traits, so passes get harder further forward, shots only come from sensible areas and
chance quality (xG) depends on distance and angle to goal.

Internally the ball position is kept in the *attacking frame* of the team in
possession (x = 0 at their own goal line, x = 105 at the goal they attack). Every
event is converted to absolute pitch coordinates before it is written.

Same seed + same clubs = the exact same match, every time.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .rosters import LEAGUE_NAME, SEASON, Club, Player, get_club
from .schema import PITCH_LENGTH as L, PITCH_WIDTH as W, SCHEMA_VERSION

HALF = 45 * 60
GOAL_Y = W / 2

# role, base x, base y (attacking frame, team shape when the ball is on halfway)
FORMATION_433 = [
    ("GK", 5, 34), ("RB", 32, 8), ("CB", 24, 25), ("CB", 24, 43), ("LB", 32, 60),
    ("DM", 42, 34), ("CM", 54, 21), ("CM", 54, 47), ("RW", 76, 9), ("ST", 84, 34), ("LW", 76, 59),
]
ROLE_GROUP = {"GK": "GK", "RB": "DEF", "CB": "DEF", "LB": "DEF", "DM": "MID", "CM": "MID",
              "RW": "ATT", "ST": "ATT", "LW": "ATT"}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass(eq=False)
class Slot:
    """A position on the pitch filled by one player."""
    player: Player
    role: str
    bx: float
    by: float


@dataclass(eq=False)
class TeamState:
    side: int  # 0 home, 1 away
    club: Club
    slots: list[Slot]
    bench: list[Player]
    yellows: dict[str, int] = field(default_factory=dict)
    sub_times: list[float] = field(default_factory=list)
    subs_made: int = 0
    score: int = 0

    @property
    def code(self) -> str:
        return self.club.code

    def pos(self, s: Slot, ball_x: float, ball_y: float) -> tuple[float, float]:
        """Where this slot stands given the ball position (both in this team's attacking frame)."""
        shift = 0.15 if s.role == "GK" else 0.45
        px = _clamp(s.bx + (ball_x - L / 2) * shift, 1.0, L - 1.0 if s.role == "GK" else L - 13.0)
        py = _clamp(s.by + (ball_y - GOAL_Y) * 0.25, 1.0, W - 1.0)
        return px, py

    def gk(self) -> Slot:
        return next(s for s in self.slots if s.role == "GK")


def _build_team(side: int, club: Club) -> TeamState:
    pool = list(club.squad)
    slots = []
    for role, bx, by in FORMATION_433:
        p = next(p for p in pool if p.position == role)
        pool.remove(p)
        slots.append(Slot(p, role, bx, by))
    return TeamState(side, club, slots, bench=pool)


class MatchSimulator:
    def __init__(self, home: str, away: str, seed: int, match_id: str | None = None,
                 matchday: int | None = None):
        if home.upper() == away.upper():
            raise ValueError("home and away must be different clubs")
        self.seed = seed
        self.rng = random.Random(seed)
        self.match_id = match_id or f"m-{home.upper()}-{away.upper()}-{seed}"
        self.matchday = matchday
        self.teams = [_build_team(0, get_club(home)), _build_team(1, get_club(away))]
        self._starters = [[s.player for s in t.slots] for t in self.teams]
        self.events: list[dict[str, Any]] = []

        self.t = 0.0  # seconds of match clock since kickoff (halftime excluded)
        self.period = 1
        self.period_start = 0.0
        self.period_end = 0.0
        self.period_lengths: list[float] = []
        self.dead_time = 0.0

        self.att = 0  # side in possession
        self.carrier: Slot | None = None
        self.ball = (L / 2, GOAL_Y)
        self.possession_id = 0
        self.set_piece: str | None = None
        self.pressure_defender: Slot | None = None
        self.last_pass: tuple[Slot, Slot, float] | None = None  # passer, receiver, time
        self.first_kickoff = self.rng.randint(0, 1)

    # ------------------------------------------------------------------ helpers
    @property
    def team(self) -> TeamState:
        return self.teams[self.att]

    @property
    def opp(self) -> TeamState:
        return self.teams[1 - self.att]

    def attacks_right(self, side: int) -> bool:
        return (side == 0) == (self.period == 1)

    def to_abs(self, side: int, x: float, y: float) -> tuple[float, float]:
        if self.attacks_right(side):
            return x, y
        return L - x, W - y

    @staticmethod
    def mirror(x: float, y: float) -> tuple[float, float]:
        """Convert a point between the two teams' attacking frames."""
        return L - x, W - y

    def _clock(self) -> tuple[int, int, int]:
        pt = self.t - self.period_start
        base = 0 if self.period == 1 else 45
        if pt < HALF:
            return base + int(pt // 60) + 1, 0, int(pt % 60)
        over = pt - HALF
        return base + 45, int(over // 60) + 1, int(over % 60)

    def emit(self, etype: str, side: int | None, slot: Slot | None = None,
             at: tuple[float, float] | None = None, end: tuple[float, float] | None = None,
             **extra: Any) -> dict[str, Any]:
        """Write one event. `at`/`end` are in the attacking frame of `side`."""
        minute, added, second = self._clock()
        seq = len(self.events)
        e: dict[str, Any] = {
            "event_id": f"{self.match_id}-{seq:05d}",
            "match_id": self.match_id,
            "seq": seq,
            "t": round(self.t, 1),
            "period": self.period,
            "minute": minute,
            "added": added,
            "second": second,
            "type": etype,
            "team": None if side is None else self.teams[side].code,
            "player_id": slot.player.player_id if slot else None,
            "possession_id": self.possession_id,
            "possession_team": self.team.code if self.possession_id else None,
        }
        if at is not None and side is not None:
            ax, ay = self.to_abs(side, *at)
            e["x"], e["y"] = round(ax, 1), round(ay, 1)
        if end is not None and side is not None:
            ex, ey = self.to_abs(side, *end)
            e["end_x"], e["end_y"] = round(ex, 1), round(ey, 1)
        for k, v in extra.items():
            if v is None:
                continue
            if k == "related":
                e["related_player_id"] = v.player.player_id if isinstance(v, Slot) else v
            elif isinstance(v, float):
                e[k] = round(v, 3) if k == "xg" else round(v, 1)
            else:
                e[k] = v
        self.events.append(e)
        return e

    def advance(self, seconds: float, dead: bool = False) -> None:
        self.t += seconds
        if dead:
            self.dead_time += seconds

    def nearest(self, team: TeamState, x: float, y: float, k: int = 3,
                exclude: Slot | None = None, outfield: bool = False) -> list[Slot]:
        """Slots of `team` nearest to (x, y) given in that team's attacking frame."""
        cands = [s for s in team.slots if s is not exclude and not (outfield and s.role == "GK")]
        return sorted(cands, key=lambda s: math.dist(team.pos(s, x, y), (x, y)))[:k]

    def pick_defender(self, x: float, y: float) -> Slot:
        """An opponent close to the ball at (x, y) in the attacking team's frame."""
        ox, oy = self.mirror(x, y)
        ranked = self.nearest(self.opp, ox, oy, k=3)
        return self.rng.choices(ranked, weights=[0.6, 0.3, 0.1][:len(ranked)])[0]

    def change_possession(self, new_side: int, carrier: Slot, at: tuple[float, float], reason: str) -> None:
        """Hand the ball to `new_side`; `at` is in the new side's attacking frame."""
        self.att = new_side
        self.carrier = carrier
        self.ball = at
        self.possession_id += 1
        self.last_pass = None
        self.emit("possession_change", new_side, details={"reason": reason})

    @staticmethod
    def goal_distance(x: float, y: float) -> float:
        return math.dist((x, y), (L, GOAL_Y))

    @staticmethod
    def xg(x: float, y: float) -> float:
        """Chance quality from distance and the angle the goal mouth opens up."""
        dx = max(0.5, L - x)
        dy = abs(y - GOAL_Y)
        d = math.hypot(dx, dy)
        angle = math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66 ** 2)
        if angle < 0:
            angle += math.pi
        return _clamp(1 / (1 + math.exp(1.45 + 0.09 * d - 1.8 * angle)), 0.01, 0.95)

    def shot_prob(self, x: float, y: float) -> float:
        """Chance the carrier shoots instead of passing or carrying, by distance band."""
        if x < 72:
            return 0.0
        d = self.goal_distance(x, y)
        bands = ((8, 0.22), (12, 0.10), (18, 0.09), (25, 0.12), (32, 0.08))
        p = next((pb for limit, pb in bands if d <= limit), 0.0)
        if abs(y - GOAL_Y) > 20:
            p *= 0.35
        return p

    # ------------------------------------------------------------------ match flow
    def play(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        for period in (1, 2):
            self.period = period
            self.period_start = self.t
            stoppage = self.rng.uniform(60, 200) if period == 1 else self.rng.uniform(180, 380)
            self.period_end = self.t + HALF + stoppage
            if period == 2:
                for team in self.teams:
                    team.sub_times = sorted(self.t + self.rng.uniform(600, 2400) for _ in range(3))
            self.emit("half_start", None)
            self.kickoff(self.first_kickoff if period == 1 else 1 - self.first_kickoff)
            while self.t < self.period_end:
                self.step()
            self.emit("half_end", None)
            self.period_lengths.append(self.t - self.period_start)
        return self.metadata(), self.events

    def kickoff(self, side: int) -> None:
        team = self.teams[side]
        taker = next((s for s in team.slots if s.role == "ST"), None) or self.nearest(
            team, L / 2, GOAL_Y, k=1, outfield=True)[0]
        self.restart(side, "kickoff", (L / 2, GOAL_Y), taker)

    def restart(self, side: int, kind: str, at: tuple[float, float], taker: Slot | None = None) -> None:
        """Dead ball: make subs if due, give the ball to `side` and restart play."""
        self.make_due_subs()
        team = self.teams[side]
        if taker is None or taker not in team.slots:
            if kind == "goal_kick":
                taker = team.gk()
            elif kind == "corner":
                wide = [s for s in team.slots if s.role in ("RW", "LW", "CM")]
                taker = self.rng.choice(wide) if wide else self.nearest(team, *at, k=1, outfield=True)[0]
            else:
                taker = self.nearest(team, *at, k=1, outfield=True)[0]
        if side != self.att or self.possession_id == 0 or kind == "kickoff":
            self.change_possession(side, taker, at, kind)
        self.carrier, self.ball = taker, at
        self.set_piece = kind
        self.emit("restart", side, taker, at, details={"kind": kind})

    def make_due_subs(self) -> None:
        for team in self.teams:
            while team.sub_times and team.sub_times[0] <= self.t:
                team.sub_times.pop(0)
                if team.subs_made >= 3 or not team.bench:
                    continue
                outfield = [s for s in team.slots if s.role != "GK"]
                weights = [3 if ROLE_GROUP[s.role] == "ATT" else 2 if ROLE_GROUP[s.role] == "MID" else 1
                           for s in outfield]
                out = self.rng.choices(outfield, weights=weights)[0]
                same = [p for p in team.bench if ROLE_GROUP[p.position] == ROLE_GROUP[out.role]]
                options = same or [p for p in team.bench if p.position != "GK"]
                if not options:
                    continue
                incoming = self.rng.choice(options)
                team.bench.remove(incoming)
                team.subs_made += 1
                self.emit("substitution", team.side, out, related=incoming.player_id,
                          details={"position": out.role})
                out.player = incoming

    def step(self) -> None:
        sp, self.set_piece = self.set_piece, None
        x, y = self.ball
        c = self.carrier
        if sp == "kickoff":
            return self.pass_ball(False, set_piece=sp, kickoff=True)
        if sp == "penalty":
            return self.shoot(False, xg_override=0.76, set_piece=sp)
        if sp == "corner":
            return self.corner_cross()
        if sp == "free_kick" and x > 72 and self.goal_distance(x, y) < 32 and self.rng.random() < 0.3:
            return self.shoot(False, xg_override=self.xg(x, y) * 0.45, set_piece=sp)
        if sp in ("throw_in", "goal_kick", "free_kick"):
            return self.pass_ball(False, set_piece=sp)

        under = False
        self.pressure_defender = None
        p_press = 0.06 if c.role == "GK" else 0.16 + 0.22 * x / L
        if self.rng.random() < p_press:
            under = True
            d = self.pick_defender(x, y)
            self.pressure_defender = d
            self.emit("pressure", 1 - self.att, d, self.mirror(x, y), related=c)
            foul_p = 0.075 * (1.4 - d.player.discipline / 100)
            if x >= L - 16.5 and abs(y - GOAL_Y) <= 20.16:
                foul_p *= 0.06  # defenders rarely risk a foul in their own box
            if c.role != "GK" and self.rng.random() < foul_p:
                self.advance(self.rng.uniform(1.0, 2.5))
                return self.foul(d, (x, y))

        if c.role != "GK":
            if self.rng.random() < self.shot_prob(x, y):
                return self.shoot(under)
            if self.rng.random() < 0.21:
                return self.carry(under)
        return self.pass_ball(under)

    # ------------------------------------------------------------------ actions
    def pass_ball(self, under: bool, set_piece: str | None = None, kickoff: bool = False) -> None:
        team, c, rng = self.team, self.carrier, self.rng
        x, y = self.ball
        mates = [s for s in team.slots if s is not c]
        long_ball = rng.random() < (0.45 if c.role == "GK" else 0.06) and not kickoff
        weights = []
        for s in mates:
            px, py = team.pos(s, x, y)
            d = math.dist((px, py), (x, y))
            fwd = px - x
            if kickoff:
                w = 1.0 if s.role in ("DM", "CM") else 0.0
            elif long_ball:
                w = 1.0 if fwd > 20 else 0.02
            else:
                w = math.exp(-d / 16) * (1 + 0.035 * _clamp(fwd, -12, 25))
            if s.role == "GK":
                w *= 0.12 if x < 35 and not kickoff else 0.0
            if set_piece == "throw_in":
                w *= 2.0 if d < 20 else 0.2
            weights.append(max(w, 0.0))
        if sum(weights) <= 0:  # e.g. no midfielders left after red cards
            weights = [0.0 if s.role == "GK" else 1.0 for s in mates]
        recv = rng.choices(mates, weights=weights)[0]
        px, py = team.pos(recv, x, y)
        tx = _clamp(px + rng.gauss(0, 2.5), 1.0, L - 1.0)
        ty = _clamp(py + rng.gauss(0, 2.5), 1.0, W - 1.0)
        dist = math.dist((tx, ty), (x, y))

        p = 0.94 - 0.006 * max(0.0, dist - 10) - (0.11 if under else 0.0) \
            - 0.12 * max(0.0, (tx - 70) / 35) + (c.player.passing - 65) * 0.0025
        if tx - x > 25:
            p -= 0.06
        if set_piece in ("throw_in", "kickoff"):
            p += 0.04
        p = _clamp(p, 0.15, 0.985)
        speed = _clamp(22 + dist * 1.6 + rng.gauss(0, 6), 15, 115)
        travel = dist / (speed / 3.6)
        details = {"length_m": round(dist, 1)}
        if set_piece:
            details["set_piece"] = set_piece
        if long_ball:
            details["long_ball"] = True

        if rng.random() < p:
            self.emit("pass", self.att, c, (x, y), (tx, ty), outcome="complete", related=recv,
                      speed_kmh=speed, under_pressure=under, details=details)
            self.advance(travel + rng.uniform(0.6, 2.2))
            self.last_pass = (c, recv, self.t)
            self.carrier, self.ball = recv, (tx, ty)
            return

        self.emit("pass", self.att, c, (x, y), (tx, ty), outcome="incomplete", related=recv,
                  speed_kmh=speed, under_pressure=under, details=details)
        if rng.random() < 0.64:
            self.advance(travel * 0.7 + 0.3)
            d = self.nearest(self.opp, *self.mirror(tx, ty), k=2)
            d = rng.choice(d)
            at = self.mirror(tx, ty)
            self.emit("interception", 1 - self.att, d, at, outcome="won", related=c)
            self.change_possession(1 - self.att, d, at, "interception")
        else:
            self.advance(travel)
            self.ball_out(tx, ty)

    def ball_out(self, tx: float, ty: float) -> None:
        """Last touch by the team in possession; restart goes to the other side."""
        side = self.att
        if tx > L - 14 and abs(ty - GOAL_Y) < 28:
            ex, ey = L, ty
            if self.rng.random() < 0.55:
                self.emit("ball_out", side, self.carrier, (ex, ey), details={"next": "corner",
                                                                           "deflected": True})
                return self.corner_for_attack(ty)
            kind = "goal_kick"
        else:
            ex, ey = tx, 0.0 if ty < GOAL_Y else W
            kind = "throw_in"
        self.emit("ball_out", side, self.carrier, (ex, ey), details={"next": kind})
        opp = 1 - side
        if kind == "goal_kick":
            at = (5.5, GOAL_Y)
            self.advance(self.rng.uniform(18, 32), dead=True)
        else:
            mx, my = self.mirror(ex, ey)
            at = (_clamp(mx, 1, L - 1), 0.0 if my < GOAL_Y else W)
            self.advance(self.rng.uniform(12, 24), dead=True)
        self.restart(opp, kind, at)

    def carry(self, under: bool) -> None:
        c, rng = self.carrier, self.rng
        x, y = self.ball
        length = rng.uniform(3, 11) * (0.8 + c.player.pace / 250)
        pull = (GOAL_Y - y) / W if x > 70 else 0.0
        a = rng.gauss(pull, 0.6)
        nx = _clamp(x + length * math.cos(a), 1.0, L - 1.0)
        ny = _clamp(y + length * math.sin(a), 1.0, W - 1.0)
        speed_ms = rng.uniform(4.0, 7.0) * (0.85 + c.player.pace / 400)

        if under and self.pressure_defender is not None:
            d = self.pressure_defender
            foul_p = 0.17 * (1.4 - d.player.discipline / 100)
            if x >= L - 16.5 and abs(y - GOAL_Y) <= 20.16:
                foul_p *= 0.06
            if rng.random() < foul_p:
                self.advance(rng.uniform(1.0, 2.5))
                return self.foul(d, (x, y))
            win_p = 0.40 + (d.player.tackling - 60) * 0.004 - (c.player.pace - 60) * 0.004
            if rng.random() < win_p:
                at = self.mirror(x, y)
                self.advance(rng.uniform(1.0, 2.5))
                self.emit("tackle", 1 - self.att, d, at, outcome="won", related=c)
                self.change_possession(1 - self.att, d, at, "tackle")
                return
            self.emit("tackle", 1 - self.att, d, self.mirror(x, y), outcome="lost", related=c)
            self.emit("carry", self.att, c, (x, y), (nx, ny), outcome="complete",
                      speed_kmh=speed_ms * 3.6, under_pressure=True,
                      details={"length_m": round(length, 1), "beat_player": d.player.player_id})
        else:
            self.emit("carry", self.att, c, (x, y), (nx, ny), outcome="complete",
                      speed_kmh=speed_ms * 3.6, under_pressure=under,
                      details={"length_m": round(length, 1)})
        self.advance(length / speed_ms)
        self.ball = (nx, ny)

    def foul(self, d: Slot, at: tuple[float, float]) -> None:
        """Defender `d` fouls the carrier at `at` (attacking frame)."""
        rng = self.rng
        x, y = at
        victim = self.carrier
        self.emit("foul", 1 - self.att, d, self.mirror(x, y), outcome="committed", related=victim)
        defending = self.opp
        card = None
        if d.role != "GK" and rng.random() < 0.006:
            card = "red"
        elif rng.random() < 0.15 + (0.08 if x > 70 else 0.0):
            n = defending.yellows.get(d.player.player_id, 0) + 1
            defending.yellows[d.player.player_id] = n
            card = "second_yellow" if n >= 2 and d.role != "GK" else "yellow"
        if card:
            self.emit("card", 1 - self.att, d, self.mirror(x, y), outcome=card)
            self.advance(rng.uniform(15, 30), dead=True)
            if card in ("red", "second_yellow"):
                defending.slots.remove(d)
        self.advance(rng.uniform(15, 35), dead=True)
        in_box = x >= L - 16.5 and abs(y - GOAL_Y) <= 20.16
        if in_box:
            self.restart(self.att, "penalty", (L - 11, GOAL_Y), victim)
        else:
            self.restart(self.att, "free_kick", (x, y), victim)

    def corner_cross(self) -> None:
        team, c, rng = self.team, self.carrier, self.rng
        x, y = self.ball
        role_w = {"CB": 3, "ST": 3, "CM": 1.5, "DM": 1, "LW": 1, "RW": 1, "LB": 0.5, "RB": 0.5, "GK": 0}
        mates = [s for s in team.slots if s is not c]
        recv = rng.choices(mates, weights=[role_w[s.role] for s in mates])[0]
        tx, ty = rng.uniform(93, 101), rng.uniform(27, 41)
        dist = math.dist((x, y), (tx, ty))
        details = {"set_piece": "corner", "cross": True, "length_m": round(dist, 1)}
        speed = rng.uniform(55, 80)
        if rng.random() < 0.32:
            self.emit("pass", self.att, c, (x, y), (tx, ty), outcome="complete", related=recv,
                      speed_kmh=speed, under_pressure=False, details=details)
            self.advance(1.4)
            self.last_pass = (c, recv, self.t)
            self.carrier, self.ball = recv, (tx, ty)
            if rng.random() < 0.62:
                return self.shoot(True, header=True)
            return
        self.emit("pass", self.att, c, (x, y), (tx, ty), outcome="incomplete", related=recv,
                  speed_kmh=speed, under_pressure=False, details=details)
        self.advance(1.6)
        d = self.nearest(self.opp, *self.mirror(tx, ty), k=1, outfield=True)[0]
        self.emit("clearance", 1 - self.att, d, self.mirror(tx, ty))
        self.advance(rng.uniform(1.5, 3.0))
        if rng.random() < 0.7:
            at = (rng.uniform(22, 40), rng.uniform(10, 58))
            winner = self.nearest(self.opp, *at, k=1, outfield=True)[0]
            self.change_possession(1 - self.att, winner, at, "clearance")
        else:
            at = (rng.uniform(70, 82), rng.uniform(15, 53))
            self.carrier = self.nearest(team, *at, k=1, outfield=True)[0]
            self.ball = at

    def shoot(self, under: bool, header: bool = False, xg_override: float | None = None,
              set_piece: str | None = None) -> None:
        c, rng = self.carrier, self.rng
        x, y = self.ball
        xg = xg_override if xg_override is not None else self.xg(x, y)
        if under:
            xg *= 0.8
        if header:
            xg *= 0.6
        finish = 0.75 + c.player.finishing / 100 * 0.4
        p_goal = min(0.95, xg * finish)
        d = self.goal_distance(x, y)
        speed = _clamp(rng.gauss(95 - (12 if header else 0) - max(0.0, 12 - d) * 1.5, 12), 40, 135)

        if rng.random() < p_goal:
            outcome = "goal"
        else:
            r = rng.random()
            if set_piece == "penalty":
                outcome = "saved" if r < 0.6 else "off_target"
            else:
                outcome = "blocked" if r < 0.27 else "saved" if r < 0.53 else "off_target"
        if outcome in ("goal", "saved"):
            end = (L, _clamp(GOAL_Y + rng.uniform(-3.4, 3.4), 0, W))
        elif outcome == "blocked":
            end = (_clamp(x + rng.uniform(1, 4), 0, L), y)
        else:
            side_miss = rng.uniform(4.5, 12) * rng.choice([-1, 1])
            end = (L, _clamp(GOAL_Y + side_miss, 0, W))

        details: dict[str, Any] = {"distance_m": round(d, 1)}
        if header:
            details["body_part"] = "head"
        if set_piece:
            details["set_piece"] = set_piece
        self.emit("shot", self.att, c, (x, y), end, outcome=outcome, xg=xg, speed_kmh=speed,
                  under_pressure=under, details=details)
        self.advance(1.5)

        if outcome == "goal":
            assister = None
            if self.last_pass and self.last_pass[1] is c and self.t - self.last_pass[2] < 10:
                assister = self.last_pass[0]
            self.team.score += 1
            self.emit("goal", self.att, c, (x, y), related=assister,
                      details={"score": {self.teams[0].code: self.teams[0].score,
                                         self.teams[1].code: self.teams[1].score}})
            self.advance(rng.uniform(50, 75), dead=True)
            self.kickoff(1 - self.att)
        elif outcome == "saved":
            gk = self.opp.gk()
            hold = rng.random() < 0.62
            gk_at = (1.0, self.mirror(*end)[1])
            self.emit("save", 1 - self.att, gk, gk_at, outcome="held" if hold else "parried", related=c)
            if hold:
                self.advance(rng.uniform(6, 12))
                self.change_possession(1 - self.att, gk, (6.0, GOAL_Y), "save")
            else:
                self.emit("ball_out", 1 - self.att, gk, (0.0, self.mirror(*end)[1]), details={"next": "corner"})
                self.corner_for_attack(y)
        elif outcome == "blocked":
            b = self.nearest(self.opp, *self.mirror(*end), k=1, outfield=True)[0]
            self.emit("block", 1 - self.att, b, self.mirror(*end), related=c)
            r = rng.random()
            if r < 0.40:
                self.emit("ball_out", 1 - self.att, b, (0.0, self.mirror(*end)[1]), details={"next": "corner"})
                self.corner_for_attack(y)
            elif r < 0.78:
                self.advance(rng.uniform(0.5, 1.5))
                self.change_possession(1 - self.att, b, self.mirror(*end), "block")
            else:
                at = (_clamp(x - rng.uniform(4, 10), 1, L - 1), _clamp(y + rng.uniform(-6, 6), 1, W - 1))
                self.advance(rng.uniform(1.0, 2.0))
                self.carrier = self.nearest(self.team, *at, k=1, exclude=c, outfield=True)[0]
                self.ball = at
        else:
            self.emit("ball_out", self.att, c, end, details={"next": "goal_kick"})
            self.advance(rng.uniform(18, 32), dead=True)
            self.restart(1 - self.att, "goal_kick", (5.5, GOAL_Y))

    def corner_for_attack(self, shot_y: float) -> None:
        self.advance(self.rng.uniform(20, 35), dead=True)
        cy = 0.5 if shot_y < GOAL_Y else W - 0.5
        self.restart(self.att, "corner", (L - 0.5, cy))

    # ------------------------------------------------------------------ output
    def metadata(self) -> dict[str, Any]:
        def side_info(team: TeamState, formation_start: list[Player]) -> dict[str, Any]:
            starters = {p.player_id for p in formation_start}
            return {
                **team.club.public(),
                "formation": "4-3-3",
                "lineup": [p.public() for p in formation_start],
                "bench": [p.public() for p in team.club.squad if p.player_id not in starters],
            }

        home, away = self.teams
        return {
            "schema_version": SCHEMA_VERSION,
            "generator": "why-generator v1",
            "match_id": self.match_id,
            "seed": self.seed,
            "competition": {"name": LEAGUE_NAME, "season": SEASON, "matchday": self.matchday},
            "venue": home.club.stadium,
            "pitch": {"length_m": L, "width_m": W},
            "home": side_info(home, self._starters[0]),
            "away": side_info(away, self._starters[1]),
            "attacking_right": {"1": home.code, "2": away.code},
            "first_kickoff": self.teams[self.first_kickoff].code,
            "result": {"home": home.score, "away": away.score},
            "duration": {
                "period_1_s": round(self.period_lengths[0], 1),
                "period_2_s": round(self.period_lengths[1], 1),
                "ball_in_play_s": round(sum(self.period_lengths) - self.dead_time, 1),
            },
            "event_count": len(self.events),
        }


def simulate_match(home: str, away: str, seed: int, match_id: str | None = None,
                   matchday: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Play one match and return (metadata, events)."""
    return MatchSimulator(home, away, seed, match_id, matchday).play()
