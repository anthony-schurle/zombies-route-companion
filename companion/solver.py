"""Exact state-space Dijkstra on the finite, authored map."""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from time import perf_counter

from .model import Action, COLD_WAR, MARKERS, MapProfile, Match, World


@dataclass(frozen=True, slots=True)
class Options:
    mode: str = "Economy"
    budget: str = "Setup"
    economy_weight: int = 50

    def __post_init__(self):
        if self.mode not in {"Economy", "Speed", "Balanced"} or self.budget not in {"Setup", "Immediate"}:
            raise ValueError("Unknown planning option")
        if not 0 <= self.economy_weight <= 100:
            raise ValueError("Economy weight must be from 0 to 100")

    def rank(self, points, seconds):
        if self.mode == "Speed":
            return seconds, points
        if self.mode == "Economy":
            return points, seconds
        w = self.economy_weight
        return w * 30 * points + (100 - w) * 1000 * seconds, points, seconds


def step_balances(steps):
    """Carry the cost of a known timed Aether trip before entering the anomaly."""
    balances = [s.required_balance for s in steps]
    for i, step in enumerate(steps):
        if not step.reserve_until:
            continue
        spent = step.cost
        needed = step.required_balance
        for later in steps[i + 1:]:
            needed = max(needed, spent + later.required_balance)
            spent += later.cost
            if later.id == step.reserve_until:
                balances[i] = needed
                break
    return balances


@dataclass(frozen=True, slots=True)
class Plan:
    status: str
    steps: tuple[Action, ...]
    cost: int
    seconds: int
    shortfall: int
    expanded: int
    milliseconds: float
    to_marker: bool = False

    def readiness(self, balance):
        """Cumulative affordability. A future free action can depend on a pending door."""
        spent = required = 0
        for step, needed in zip(self.steps, step_balances(self.steps)):
            required = max(required, spent + needed)
            spent += step.cost
            yield max(0, required - balance)


@dataclass(slots=True, eq=False)
class Label:
    world: World
    cost: int
    seconds: int
    parent: Label | None = None
    step: Action | None = None
    live: bool = True


def _search(profile, start, goals, prohibited, options, balance, first_forced=None):
    root = Label(start, 0, 0)
    ids = count()
    queue = [(options.rank(0, 0), next(ids), root)]
    def location_key(world):
        return (world.zone, world.opened, world.flags)

    frontier = {location_key(start): [root]}
    expanded = 0
    capped = options.budget == "Immediate"
    # A faster, more expensive arrival can exhaust the cash needed later.
    # Keep the Pareto frontier for budget-constrained speed/weighted searches.
    multi = capped and options.mode != "Economy"
    def dominates(a_cost, a_time, a_cooldown, b_cost, b_time, b_cooldown):
        if a_cooldown > b_cooldown:
            return False
        if multi:
            return a_cost <= b_cost and a_time <= b_time
        return options.rank(a_cost, a_time) <= options.rank(b_cost, b_time)

    while queue:
        _, _, node = heappop(queue)
        if not node.live:
            continue
        if goals <= node.world.flags:
            return node, expanded
        expanded += 1
        options_here = (first_forced,) if first_forced is not None and node is root else profile.valid_actions(node.world, prohibited)
        for step in options_here:
            if capped and node.cost + step.required_balance > balance:
                continue
            world = step.advance(node.world)
            cost, seconds = node.cost + step.cost, node.seconds + step.seconds
            # The initial booth visit can have insufficient cash. A later funded
            # visit must remain distinguishable even if its topology is identical.
            key = location_key(world)
            if first_forced and key == location_key(start):
                key = (key, "funded")
            labels = frontier.get(key, [])
            # A shorter remaining cooldown can reproduce every future route
            # available to an otherwise identical later-ready arrival.
            if any(dominates(other.cost, other.seconds, other.world.cooldown,
                             cost, seconds, world.cooldown) for other in labels):
                continue
            keep = []
            for other in labels:
                if dominates(cost, seconds, world.cooldown,
                             other.cost, other.seconds, other.world.cooldown):
                    other.live = False
                else:
                    keep.append(other)
            nxt = Label(world, cost, seconds, node, step)
            frontier[key] = keep + [nxt]
            heappush(queue, (options.rank(cost, seconds), next(ids), nxt))
    return None, expanded


def find_route(profile: MapProfile, match: Match, goals, options=Options(), prohibited=frozenset()):
    start_time = perf_counter()
    profile.validate_match(match)
    goals = frozenset(goals)
    if not goals <= profile.goals.keys() or not set(prohibited) <= profile.doors.keys():
        raise ValueError("Unknown target or prohibited door")
    flags = match.world.flags
    to_marker = (profile.data["id"] == COLD_WAR and bool(goals & {"forged", "packed"}) and
                 not flags & (MARKERS | {"part", "forged"}))
    if (profile.data["id"] == COLD_WAR and goals & {"forged", "packed"} and
            "part" in flags and "aether" not in flags):
        return Plan("visit_required", (), 0, 0, 0, 0, (perf_counter() - start_time) * 1000)
    if to_marker:
        if options.budget == "Immediate" or "aether" in flags:
            return Plan("marker_required", (), 0, 0, 0, 0, (perf_counter() - start_time) * 1000, True)
        goals = frozenset({"aether"})
    # Points cannot be earned inside Kino's temporary projector room. An
    # unfunded visit must end before the player can plan a funded upgrade.
    forced = None
    if profile.data["id"] == "bo1-kino-solo" and match.world.zone == "projector" and "packed" not in match.world.flags:
        upgrade_cost = profile.actions["upgrade"]["cost"]
        if match.points < upgrade_cost:
            forced = next(a for a in profile.valid_actions(match.world) if a.id == "return_empty")
    result, expanded = _search(profile, match.world, goals, prohibited, options, match.points, forced)
    status = "found" if result else "unreachable"
    cost = seconds = shortfall = 0
    steps = ()
    if result is None and options.budget == "Immediate":
        fallback, extra = _search(profile, match.world, goals, prohibited, Options(), match.points, forced)
        expanded += extra
        if fallback:
            status = "over_budget"
            result = fallback
    if result:
        cost, seconds = result.cost, result.seconds
        reverse = []
        while result.step is not None:
            reverse.append(result.step)
            result = result.parent
        sequence = tuple(reversed(reverse))
        required = spent = 0
        for step, needed in zip(sequence, step_balances(sequence)):
            required = max(required, spent + needed)
            spent += step.cost
        shortfall = max(0, required - match.points)
        if status == "found":
            steps = sequence
            if not steps:
                status = "complete" if goals else "no_targets"
    return Plan(status, steps, cost, seconds, shortfall, expanded, (perf_counter() - start_time) * 1000, to_marker)
