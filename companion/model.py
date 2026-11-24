"""Map validation and deterministic, immutable game transitions."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from jsonschema import Draft202012Validator

MAPS = Path(__file__).resolve().parent.parent / "maps"
DEFAULT_MAP = MAPS / "kino_der_toten.json"
MAP_FILES = {"kino": DEFAULT_MAP, "die-maschine": MAPS / "die_maschine.json"}
COLD_WAR = "cw-die-maschine-solo"
MARKERS = frozenset({"marker_crash", "marker_pond"})
Flags = frozenset[str]


@dataclass(frozen=True, slots=True)
class World:
    zone: str
    opened: Flags = frozenset()
    flags: Flags = frozenset()
    cooldown: int = 0
    other_perks: int = 0


@dataclass(frozen=True, slots=True)
class Match:
    world: World
    points: int


@dataclass(frozen=True, slots=True)
class Action:
    id: str
    label: str
    origin: str
    dest: str
    cost: int
    seconds: int
    door: str = ""
    gives: Flags = frozenset()
    takes: Flags = frozenset()
    requires: Flags = frozenset()
    absent: Flags = frozenset()
    reserve: int = 0
    cooldown_after: int = 0
    needs_ready: bool = False
    reserve_until: str = ""

    @property
    def required_balance(self) -> int:
        return max(self.cost, self.reserve)

    def advance(self, world: World) -> World:
        opened = world.opened | {self.door} if self.door else world.opened
        flags = (world.flags - self.takes) | self.gives if self.takes or self.gives else world.flags
        return World(self.dest, opened, flags, max(self.cooldown_after, world.cooldown - self.seconds, 0), world.other_perks)


def index(rows):
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate identifier within a map collection")
    return result


class MapProfile:
    def __init__(self, data):
        schema = json.loads((MAPS / "schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(data)
        self.data = data
        self.zones = index(data["zones"])
        self.edges = index(data["edges"])
        self.goals = index(data["goals"])
        self.flags = frozenset(data["flags"])
        self.doors = {k: e for k, e in self.edges.items() if e["price"]}
        self.actions = index(data["actions"])
        self.passages = defaultdict(list)
        self.interactions = defaultdict(list)
        self.initial = Match(World(data["spawn"]), data["starting_points"])

        def require(identifiers, valid, field):
            bad = set(identifiers) - set(valid)
            if bad:
                raise ValueError(f"Unknown {field}: {', '.join(sorted(bad))}")

        pricing = data.get("perk_pricing", {})
        self.perk_flags = frozenset(pricing.get("flags", []))
        self.perk_increment = pricing.get("increment", 0)
        self.other_perk_limit = pricing.get("other_max", 0)
        require(self.perk_flags, self.goals, "tracked perk")
        require([data["spawn"]], self.zones, "spawn")
        require(self.goals, self.flags, "goal flag")
        require([g["zone"] for g in self.goals.values()], self.zones, "goal zone")
        for edge in self.edges.values():
            a, b = edge["from"], edge["to"]
            require([a, b], self.zones, "passage endpoint")
            needs = frozenset(edge.get("requires", []))
            require(needs, self.flags, "passage requirement")
            for origin, dest in ([(a, b), (b, a)] if edge["bidirectional"] else [(a, b)]):
                name = self.zones[dest]["name"]
                common = dict(id=edge["id"], origin=origin, dest=dest, requires=needs)
                walk = Action(**common, label=f"Go to {name}", cost=0, seconds=edge["seconds"])
                buy = Action(**common, label=f"Open door to {name}", cost=edge["price"],
                             seconds=edge["seconds"] + 1, door=edge["id"]) if edge["price"] else None
                self.passages[origin].append((walk, buy))
        for row in self.actions.values():
            specs = {key: frozenset(row.get(key, [])) for key in ("gives", "takes", "requires", "absent")}
            for key, flags in specs.items():
                require(flags, self.flags, key)
            if specs["requires"] & specs["absent"] or specs["gives"] & specs["takes"]:
                raise ValueError(f"Contradictory flags on {row['id']}")
            if "reserve_until" in row:
                require([row["reserve_until"]], self.actions, "funding checkpoint")
            dest = row.get("to", row["at"])
            require([row["at"], dest], self.zones, "interaction zone")
            self.interactions[row["at"]].append(Action(row["id"], row["name"], row["at"], dest,
                row["cost"], row["seconds"], reserve=row.get("reserve", 0), cooldown_after=row.get("cooldown_after", 0),
                needs_ready=row.get("needs_ready", False), reserve_until=row.get("reserve_until", ""), **specs))

    @classmethod
    def load(cls, path=DEFAULT_MAP):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def perk_surcharge(self, world):
        return self.perk_increment * (world.other_perks + len(self.perk_flags & world.flags))

    def validate_match(self, match: Match):
        world = match.world
        if world.zone not in self.zones or not world.opened <= self.doors.keys() or not world.flags <= self.flags:
            raise ValueError("Match contains an unknown room, door or flag")
        if type(match.points) is not int or match.points < 0:
            raise ValueError("Points must be a nonnegative whole number")
        if type(world.cooldown) is not int or world.cooldown < 0:
            raise ValueError("Cooldown must be a nonnegative whole number of seconds.")
        if type(world.other_perks) is not int or not 0 <= world.other_perks <= self.other_perk_limit:
            raise ValueError(f"Other perks must be between 0 and {self.other_perk_limit}.")
        if self.data["id"] == COLD_WAR:
            flags = world.flags
            if world.cooldown:
                raise ValueError("Die Maschine has no Kino teleporter cooldown.")
            if MARKERS <= flags:
                raise ValueError("Select one marked Aether Tunnel.")
            if flags & {"hydro", "cyclotron", "aether", "part", "forged", "packed"} and "power" not in flags:
                raise ValueError("These facilities require main power.")
            if "aether" in flags and not {"hydro", "cyclotron"} <= flags:
                raise ValueError("Activate both terminals for a Dark Aether visit.")
            if "packed" in flags and "forged" not in flags:
                raise ValueError("Mark the machine forged for a tier I upgrade.")
            if "forged" in flags and flags & {"aether", "part"}:
                raise ValueError("Forging installs the part and ends the setup visit.")
        if self.data["id"] == "bo1-kino-solo":
            powered = {"jug", "speed", "packed", "primed", "linked"}
            if "power" not in world.flags and (world.flags & powered or world.zone in {"theater", "projector"}):
                raise ValueError("Enable power for this room, perk or teleporter state.")
            if world.cooldown and ("power" not in world.flags or world.flags & {"primed", "linked"} or world.zone == "projector"):
                raise ValueError("Cooldown requires power, an idle pad and a room outside the projector room.")
            if {"primed", "linked"} <= world.flags:
                raise ValueError("Select one teleporter state.")
            if world.zone == "projector" and world.flags & {"primed", "linked"}:
                raise ValueError("The teleporter link is consumed on arrival in the projector room.")

    def valid_actions(self, world: World, prohibited=frozenset()):
        for walk, buy in self.passages[world.zone]:
            if not walk.requires <= world.flags:
                continue
            if buy and buy.door not in world.opened:
                if buy.door not in prohibited:
                    yield buy
            else:
                yield walk
        for action in self.interactions[world.zone]:
            if action.requires <= world.flags and not action.absent & world.flags:
                if action.needs_ready and world.cooldown:
                    yield Action("wait_cooldown", "Wait for teleporter cooldown", world.zone, world.zone, 0, world.cooldown)
                elif self.perk_flags & action.gives:
                    yield replace(action, cost=action.cost + self.perk_surcharge(world))
                else:
                    yield action

    def apply(self, match: Match, action: Action, prohibited=frozenset()):
        if action not in self.valid_actions(match.world, prohibited):
            raise ValueError("The route has changed. Check the next recommended step.")
        if match.points < action.required_balance:
            raise ValueError(f"This step needs {action.required_balance:,} points on hand.")
        result = Match(action.advance(match.world), match.points - action.cost)
        self.validate_match(result)
        return result
