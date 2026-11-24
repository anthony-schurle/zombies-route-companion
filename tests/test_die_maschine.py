"""Solo Cold War fixtures, acquisition order and the match-specific tunnel reveal."""
from dataclasses import replace
import unittest

from companion.model import MAP_FILES, MapProfile, Match, World
from companion.solver import Options, find_route, step_balances


class DieMaschineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = MapProfile.load(MAP_FILES["die-maschine"])

    def start(self, zone="yard", points=500, flags=(), opened=(), other_perks=0):
        return Match(World(zone, frozenset(opened), frozenset(flags), other_perks=other_perks), points)

    def test_hand_counted_solo_purchases(self):
        start = self.start(flags=["marker_crash"])
        for goals, spend in [(["jug"],4750), (["power"],8250), (["speed"],10750),
                             (["forged"],8750), (["packed"],13750), (self.map.goals,19250)]:
            with self.subTest(goals=goals):
                r = find_route(self.map, start, goals)
                self.assertEqual((r.status, r.cost), ("found", spend))

    def test_unseen_marker_is_not_a_choice_for_the_solver(self):
        start = self.start()
        plan = find_route(self.map, start, ["packed"])
        self.assertTrue(plan.to_marker)
        self.assertEqual(plan.steps[-1].id, "enter")
        self.assertFalse(any(step.id.endswith("_tube") for step in plan.steps))
        self.assertEqual(find_route(self.map, start, ["packed"], Options(budget="Immediate")).status, "marker_required")
        inside = self.start("accelerator", flags=["power","hydro","cyclotron","aether"])
        wait = find_route(self.map, inside, ["packed"])
        self.assertEqual((wait.status, wait.steps), ("marker_required", ()))
        self.assertFalse(find_route(self.map, start, ["power"]).to_marker)

    def test_both_tunnels_and_reconstructed_match(self):
        for marker, surface, destination in [("marker_crash","crash","medical"),("marker_pond","pond","weapons")]:
            with self.subTest(marker=marker):
                start = self.start(points=30000, flags=[marker])
                route = find_route(self.map, start, self.map.goals)
                spent = 0
                current = start
                for step in route.steps:
                    if step.id.endswith("_tube"):
                        self.assertEqual((step.origin, step.dest, step.cost), (surface, destination, 500))
                        self.assertTrue({"power","hydro","cyclotron","aether",marker} <= current.world.flags)
                    if step.id == "forge":
                        self.assertTrue({"aether","part"} <= current.world.flags)
                    if step.id == "upgrade":
                        self.assertIn("forged", current.world.flags)
                    current = self.map.apply(current, step)
                    spent += step.cost
                self.assertTrue(self.map.goals.keys() <= current.world.flags)
                self.assertFalse({"part","aether"} & current.world.flags)
                self.assertEqual(start.points - current.points, spent)
                self.assertEqual(spent, route.cost)

    def test_perk_prices_include_observed_and_planned_perks(self):
        early = self.start("crash", flags=[], other_perks=2)
        route = find_route(self.map, early, ["jug"])
        self.assertEqual([s.cost for s in route.steps], [3500])
        observed = self.start("medical", flags=["power","jug"], other_perks=2)
        self.assertEqual(find_route(self.map, observed, ["speed"]).cost, 4000)
        r = find_route(self.map, self.start(flags=["marker_crash"], other_perks=2), self.map.goals)
        self.assertEqual(sorted(a.cost for a in r.steps if a.gives & {"jug","speed"}), [3500,4000])
        self.assertFalse(any(a.id == "speed_machine" for a in self.map.valid_actions(World("medical"))))

    def test_power_and_door_restrictions(self):
        power = frozenset({"power"})
        self.assertFalse(any(a.dest == "main_power" for a in self.map.valid_actions(World("yard"))))
        self.assertTrue(any(a.dest == "main_power" for a in self.map.valid_actions(World("yard",flags=power))))
        r = find_route(self.map, self.start(), ["power"], prohibited={"medical_debris"})
        self.assertIn("weapons_debris", [step.id for step in r.steps])
        self.assertEqual(r.cost, 8250)
        self.assertEqual(find_route(self.map, self.start(), ["power"], prohibited={"yard_outpost"}).status,"unreachable")
        r = find_route(self.map, self.start(opened=["yard_outpost"]), ["power"])
        self.assertEqual(r.cost, 7750)

    def test_funds_for_timed_trip_and_immediate_budget(self):
        opened = ["yard_outpost","stairs","bedroom_exit","crash_tunnel","medical_debris","medical_gate","power_door"]
        activated = ["power","hydro","cyclotron","marker_pond"]
        start = self.start("accelerator", points=500, flags=activated, opened=opened)
        r = find_route(self.map, start, ["forged"])
        self.assertEqual((r.steps[0].id,step_balances(r.steps)[0]), ("enter", 2000))
        self.assertEqual(next(r.readiness(start.points)),1500)
        self.assertEqual(find_route(self.map, start, ["forged"], Options(budget="Immediate")).status,"over_budget")
        funded = replace(start,points=2000)
        self.assertEqual(find_route(self.map, funded, ["forged"], Options(budget="Immediate")).status,"found")

    def test_forged_machine_and_expired_visit(self):
        forged = self.start("accelerator",flags=["power","forged"])
        plan = find_route(self.map, forged, ["packed"])
        self.assertEqual([s.id for s in plan.steps],["upgrade"])
        expired = self.start("medical",flags=["power","part","hydro","cyclotron"])
        self.assertEqual(find_route(self.map, expired, ["packed"]).status,"visit_required")
        resumed = replace(expired,world=replace(expired.world,flags=expired.world.flags | {"aether"}))
        self.assertFalse(find_route(self.map, resumed, ["packed"]).to_marker)

    def test_contradictory_observations_are_rejected(self):
        for state in [self.start(flags=["marker_crash","marker_pond"]), self.start(flags=["power","aether"]),
                      self.start(flags=["packed"]), self.start(other_perks=9)]:
            with self.assertRaises(ValueError):
                self.map.validate_match(state)
