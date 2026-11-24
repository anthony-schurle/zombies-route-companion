import unittest

from companion.model import MapProfile, Match, World
from companion.solver import find_route


class TeleporterTests(unittest.TestCase):
    def test_cooldown_overlaps_movement(self):
        p = MapProfile.load()
        match = Match(World("projector",flags=frozenset({"power"})),4000)
        plan = find_route(p,match,["packed"])
        ids = [a.id for a in plan.steps]
        self.assertEqual(ids[0],"return_empty")
        self.assertIn("wait_cooldown",ids)
        self.assertLess(next(a.seconds for a in plan.steps if a.id=="wait_cooldown"),60)
        for step in plan.steps:
            if step.id=="ride":
                match=Match(match.world,5000)
            match=p.apply(match,step)
        self.assertIn("packed",match.world.flags)

    def test_no_wait_when_only_returning_for_perk(self):
        p=MapProfile.load()
        match=Match(World("projector",flags=frozenset({"power"})),3000)
        plan=find_route(p,match,["jug"])
        self.assertEqual([s.id for s in plan.steps],["return_empty","front","jug_machine"])
        self.assertEqual(plan.seconds,30+5+3)
