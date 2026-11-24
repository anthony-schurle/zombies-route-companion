import copy
import unittest
from dataclasses import replace

from jsonschema.exceptions import ValidationError

from companion.model import MapProfile, Match, World
from companion.session import Session
from companion.solver import Options, find_route


class KinoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = MapProfile.load()

    def plan(self, goals, zone="lobby", points=500, flags=(), opened=(), avoid=(), **options):
        start = Match(World(zone,frozenset(opened),frozenset(flags)),points)
        return find_route(self.p,start,goals,Options(**options),frozenset(avoid))

    def test_hand_calculated_costs(self):
        # Four doors cost 750+1000+1250+1250 on either wing. Adding each
        # powered utility once gives an independent lower bound, attained here.
        for goals,expected in [(["power"],4250),(["jug"],6750),(["speed"],7250),
                               (["packed"],9250), (list(self.p.goals),14750)]:
            with self.subTest(goals=goals):
                route = self.plan(goals)
                self.assertEqual(route.cost,expected)
                self.assertEqual(route.shortfall,expected-500)

    def test_every_target_subset_can_be_replayed(self):
        from itertools import combinations
        for count in range(1,5):
            for targets in combinations(self.p.goals,count):
                match = replace(self.p.initial,points=20000)
                route = find_route(self.p,match,targets)
                for step in route.steps:
                    match = self.p.apply(match,step)
                self.assertTrue(set(targets) <= match.world.flags)
                self.assertEqual(20000-match.points,route.cost)
                self.assertEqual(sum(a.seconds for a in route.steps),route.seconds)

    def test_full_route_uses_one_wing(self):
        r = self.plan(self.p.goals)
        self.assertEqual([a.door for a in r.steps if a.door],
                         ["stairs","foyer_door","dressing_door","stage_right"])

    def test_already_open_door_is_free_both_ways(self):
        start = Match(World("lobby",frozenset({"stairs"})),500)
        forth = next(a for a in self.p.valid_actions(start.world) if a.dest=="upper")
        there = self.p.apply(start,forth)
        back = next(a for a in self.p.valid_actions(there.world) if a.dest=="lobby")
        self.assertEqual(self.p.apply(there,back),start)
        self.assertGreater(back.seconds,0)
        self.assertEqual(self.plan(["power"],opened={"stairs"}).cost,3500)

    def test_power_and_teleporter_preconditions(self):
        self.assertFalse(any(a.dest=="theater" for a in self.p.valid_actions(self.p.initial.world)))
        self.assertFalse(any(a.id=="jug_machine" for a in self.p.valid_actions(World("theater"))))
        route=self.plan(["packed"])
        ids=[a.id for a in route.steps]
        critical=["switch","prime","link","ride","upgrade"]
        self.assertEqual([a for a in ids if a in critical],critical)
        ride=next(a for a in route.steps if a.id=="ride")
        self.assertEqual(ride.cost,0)
        self.assertEqual(ride.required_balance,5000)
        match=Match(World("stage",flags=frozenset({"power","linked"})),5000)
        arrived=self.p.apply(match,ride)
        self.assertNotIn("linked",arrived.world.flags)
        self.assertFalse(any(a.dest=="stage" for a in self.p.valid_actions(arrived.world)))

    def test_temporary_booth_without_funds_must_return(self):
        r=self.plan(["packed"], zone="projector",flags=["power"],points=4999)
        self.assertEqual(r.steps[0].id,"return_empty")
        self.assertEqual(r.steps[-2].id,"ride")
        self.assertEqual(r.shortfall,1)
        immediate=self.plan(["packed"],zone="projector",flags=["power"],points=4999,budget="Immediate")
        self.assertEqual(immediate.status,"over_budget")

    def test_pending_step_propagates_to_free_steps(self):
        r=self.plan(["packed"],zone="stage",flags=["power","linked"],points=4999)
        self.assertEqual(r.steps[0].id,"ride")
        self.assertEqual(list(r.readiness(4999)),[1,1])
        with self.assertRaises(ValueError):
            self.p.apply(Match(World("stage",flags=frozenset({"power","linked"})),4999),r.steps[0])

    def test_recovery_from_current_map_state(self):
        r=self.plan(["power","jug"],zone="stage",flags=["power"],points=2500,budget="Immediate")
        self.assertEqual(r.cost,2500)
        self.assertEqual([a.id for a in r.steps],["curtain","jug_machine"])

    def test_restrictions_and_unreachable(self):
        r=self.plan(["power"],avoid=["lower_door"])
        self.assertEqual(r.steps[0].dest,"upper")
        for budget in ("Setup","Immediate"):
            self.assertEqual(self.plan(["power"],avoid=["lower_door","stairs"],budget=budget).status,"unreachable")

    def test_exact_budget_and_one_point_short(self):
        for mode in ("Economy","Speed","Balanced"):
            self.assertEqual(self.plan(self.p.goals,points=14750,mode=mode,budget="Immediate").status,"found")
            low=self.plan(self.p.goals,points=14749,mode=mode,budget="Immediate")
            self.assertEqual((low.status,low.steps,low.shortfall),("over_budget",(),1))

    def test_empty_and_satisfied(self):
        self.assertEqual(self.plan([]).status,"no_targets")
        self.assertEqual(self.plan(["power"],flags=["power"]).status,"complete")

    def test_structural_validation(self):
        for kind in ("duplicate","reference","negative","flag","contradiction"):
            with self.subTest(kind=kind):
                data=copy.deepcopy(self.p.data)
                if kind=="duplicate": data["zones"].append(data["zones"][0])
                if kind=="reference": data["edges"][0]["to"]="typo"
                if kind=="negative": data["actions"][0]["cost"]=-1
                if kind=="flag": data["actions"][0]["requires"]=["typo"]
                if kind=="contradiction": data["actions"][0]["requires"]=["power"]
                with self.assertRaises((ValueError,ValidationError)):
                    MapProfile(data)

    def test_manual_correction_does_not_charge_or_infer_doors(self):
        s=Session(self.p)
        new=Match(World("foyer"),3250)
        s.record("STATE_CORRECTED","Moved to Foyer",new)
        self.assertEqual(s.match.world.opened,frozenset())
        r=find_route(self.p,s.match,["power"])
        self.assertEqual(r.cost,2500)
        s.undo()
        self.assertEqual(s.match,self.p.initial)

    def test_invalid_or_stale_confirmation_is_atomic(self):
        s=Session(self.p)
        step=find_route(self.p,s.match,["power"]).steps[0]
        with self.assertRaises(ValueError): s.confirm(step)
        self.assertEqual(s.history,[])
        s.record("POINTS_UPDATED","Balance",replace(s.match,points=750))
        s.confirm(step)
        self.assertEqual(s.match.points,0)
        self.assertIn(step.door,s.match.world.opened)
        with self.assertRaises(ValueError): s.confirm(step)
        self.assertEqual(len(s.history),2)
        s.undo()
        self.assertEqual(s.match.world,self.p.initial.world)

    def test_conflicting_state_rejected_and_undo_restores_restrictions(self):
        s=Session(self.p)
        with self.assertRaises(ValueError):
            s.record("STATE_CORRECTED","Bad update",Match(World("theater"),500))
        self.assertFalse(s.history)
        s.record("STATE_CORRECTED","Save door",s.match,{"stairs"})
        s.reset()
        self.assertFalse(s.prohibited)
        s.undo()
        self.assertEqual(s.prohibited,{"stairs"})

    def test_speed_search_keeps_affordable_slow_arrival(self):
        # The direct (fast) route spends 10, leaving too little for a 10-point
        # goal. Both paths merge into exactly the same world at room b.
        data=copy.deepcopy(self.p.data)
        data.update(id="fixture",spawn="a",flags=["done"],
                    goals=[dict(id="done",name="Target",zone="b",price=10)],
                    zones=[dict(id=k,name=k,x=0,y=0) for k in "abc"],
                    edges=[{"id":"ac","from":"a","to":"c","price":0,"seconds":5,"bidirectional":False},
                           {"id":"cb","from":"c","to":"b","price":0,"seconds":5,"bidirectional":False}],
                    actions=[dict(id="fast",name="Fast transfer",at="a",to="b",seconds=1,cost=10),
                             dict(id="finish",name="Finish",at="b",gives=["done"],absent=["done"],seconds=1,cost=10)])
        p=MapProfile(data)
        start=replace(p.initial,points=10)
        schedule=lambda mode,budget:find_route(p,start,["done"],Options(mode,budget))
        self.assertEqual(schedule("Speed","Setup").cost,20)
        self.assertEqual(schedule("Economy","Setup").cost,10)
        self.assertEqual(schedule("Speed","Immediate").seconds,11)
        self.assertEqual(schedule("Balanced","Immediate").seconds,11)
        self.assertEqual(find_route(p,start,["done"],Options("Balanced","Setup",100)).cost,10)
        self.assertEqual(find_route(p,start,["done"],Options("Balanced","Setup",0)).cost,20)
        self.assertFalse(any(a.dest=="a" for a in p.valid_actions(World("c"))))
