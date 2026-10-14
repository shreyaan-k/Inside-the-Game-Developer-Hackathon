"""Fictional league: clubs and squads.

Everything here is invented. Club names, colors and player names are generated so they
do not refer to any real club or person. Squads are deterministic: the same club code
always produces the same players, numbers and traits.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

LEAGUE_NAME = "Meridian League"
SEASON = "2026-27"



@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    number: int
    position: str  # GK, RB, CB, LB, DM, CM, RW, ST, LW
    pace: int  # 1-99 traits
    passing: int
    finishing: int
    tackling: int
    discipline: int
    stamina: int

    def public(self) -> dict:
        return {"player_id": self.player_id, "name": self.name, "number": self.number,
                "position": self.position}


@dataclass(frozen=True)
class Club:
    code: str
    name: str
    city: str
    stadium: str
    colors: tuple[str, str]
    style: str  # placeholder for v2 team styles
    squad: tuple[Player, ...] = field(repr=False)

    def public(self) -> dict:
        return {"code": self.code, "name": self.name, "city": self.city, "stadium": self.stadium,
                "colors": list(self.colors), "style": self.style}


_CLUB_SPECS = [
    # code, name, city, stadium, colors, style
    ("RVR", "Riverton Vale", "Riverton", "Millrace Park", ("#1f4e79", "#f2c14e"), "possession"),
    ("HBR", "Harbor Bay", "Harbor Bay", "Lantern Quay", ("#b23a48", "#f5f5f5"), "high_press"),
    ("KST", "Kestrel Town", "Kestrel", "The Aerie", ("#2e7d32", "#111111"), "counter"),
    ("ASH", "Ashmoor Athletic", "Ashmoor", "Cinder Lane", ("#6d4c41", "#ffd54f"), "low_block"),
    ("CRN", "Corrin City", "Corrin", "Glassworks Stadium", ("#00838f", "#ffffff"), "possession"),
    ("NGR", "Northgate Rovers", "Northgate", "Beacon Hill", ("#4527a0", "#ff7043"), "direct"),
    ("ELF", "Ellisford", "Ellisford", "The Weir", ("#c62828", "#212121"), "high_press"),
    ("SMF", "Saltmarsh", "Saltmarsh", "Tidewater Road", ("#f9a825", "#263238"), "counter"),
]

_FIRST = ["Tomas", "Aric", "Delano", "Marek", "Ilyes", "Kofi", "Rui", "Soren", "Teo", "Jalen",
          "Bram", "Elio", "Nikos", "Hamza", "Joel", "Remy", "Oskar", "Idris", "Luca", "Mateo",
          "Callum", "Yannick", "Darius", "Felix", "Kian", "Jonah", "Ezra", "Levi", "Malo",
          "Anders", "Sami", "Nuno", "Kenji", "Tariq", "Emre", "Viktor", "Oren", "Bastian"]
_SUR_A = ["Var", "Kel", "Mor", "Dan", "Ost", "Bel", "Har", "Lund", "Cor", "Tal", "Ren", "Vas",
          "Bren", "Hol", "Mar", "Ser", "Quin", "Ald", "Tor", "Ves", "Kal", "Dor", "Fen", "Gal"]
_SUR_B = ["ane", "strom", "ovic", "well", "ard", "sen", "ini", "ez", "ley", "ach", "oni", "berg",
          "ou", "ski", "ton", "ado", "vik", "ari", "elle", "mond", "ström", "ani", "ock", "eira"]

# position -> how many in the squad, and squad numbers to use
_SQUAD_SHAPE = [
    ("GK", [1, 13]), ("RB", [2, 22]), ("CB", [4, 5, 15]), ("LB", [3, 23]), ("DM", [6, 16]),
    ("CM", [8, 10, 18]), ("RW", [7, 17]), ("ST", [9, 19]), ("LW", [11, 21]),
]

# trait baselines per position: pace, passing, finishing, tackling
_BASE = {
    "GK": (45, 55, 15, 30), "RB": (74, 66, 40, 68), "CB": (60, 64, 35, 76), "LB": (74, 66, 40, 68),
    "DM": (60, 74, 45, 72), "CM": (66, 76, 58, 60), "RW": (82, 70, 68, 38), "ST": (76, 62, 78, 34),
    "LW": (82, 70, 68, 38),
}


def _clip(v: float) -> int:
    return int(max(20, min(97, round(v))))


def _make_squad(code: str) -> tuple[Player, ...]:
    rng = random.Random(f"squad:{code}")
    used: set[str] = set()
    players: list[Player] = []
    for pos, numbers in _SQUAD_SHAPE:
        for i, num in enumerate(numbers):
            while True:
                name = f"{rng.choice(_FIRST)} {rng.choice(_SUR_A)}{rng.choice(_SUR_B)}"
                if name not in used:
                    used.add(name)
                    break
            starter = i == 0
            boost = 4 if starter else -3
            pace, passing, finishing, tackling = (_clip(b + boost + rng.gauss(0, 6)) for b in _BASE[pos])
            players.append(Player(
                player_id=f"{code}-{num:02d}", name=name, number=num, position=pos,
                pace=pace, passing=passing, finishing=finishing, tackling=tackling,
                discipline=_clip(rng.gauss(70, 10)), stamina=_clip(rng.gauss(72, 8)),
            ))
    # Two stars per club: bump the starting #9 and one starting creator.
    star_ids = {f"{code}-09", f"{code}-{rng.choice([7, 10, 11]):02d}"}
    out = []
    for p in players:
        if p.player_id in star_ids:
            p = Player(**{**p.__dict__, "finishing": _clip(p.finishing + 8), "passing": _clip(p.passing + 6),
                          "pace": _clip(p.pace + 4)})
        out.append(p)
    return tuple(out)


CLUBS: dict[str, Club] = {
    code: Club(code, name, city, stadium, colors, style, _make_squad(code))
    for code, name, city, stadium, colors, style in _CLUB_SPECS
}


def get_club(code: str) -> Club:
    try:
        return CLUBS[code.upper()]
    except KeyError:
        raise KeyError(f"unknown club {code!r}; choose from {sorted(CLUBS)}") from None
