"""Offscreen desktop integration tests. Uses the installed supported Qt binding."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
try:
    from companion.ui import Companion, StateEditor, W, configure_app
except ModuleNotFoundError as exc:
    if exc.name not in {"PyQt5","PyQt6"}:
        raise
    Companion = None


@unittest.skipIf(Companion is None,"Install a supported Qt binding for the desktop tests")
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = W.QApplication.instance() or W.QApplication([])
        configure_app(cls.app)

    def setUp(self):
        self.win = Companion()
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.app.processEvents()

    def test_balance_confirm_undo_and_reset_replan(self):
        w = self.win
        self.assertFalse(w.confirm_button.isEnabled())
        w.points.setValue(3250)
        self.assertTrue(w.confirm_button.isEnabled())
        first = w.plan.steps[0]
        w.confirm_button.click()
        self.assertEqual(w.zone.currentData(),first.dest)
        self.assertEqual(w.points.value(),2500)
        self.assertEqual(w.plan.cost,6000)
        w.undo_button.click()
        self.assertEqual(w.plan.cost,6750)
        self.assertEqual(w.points.value(),3250)
        w.reset_button.click()
        self.assertEqual(w.session.match,w.profile.initial)

    def test_targets_policy_and_weight(self):
        w = self.win
        w.budget.setCurrentIndex(w.budget.findData("Immediate"))
        self.assertEqual(w.plan.status,"over_budget")
        self.assertEqual(w.route_table.rowCount(),0)
        self.assertIn("6,250",w.action_meta.text())
        w.budget.setCurrentIndex(w.budget.findData("Setup"))
        for box in w.target_boxes.values():
            box.setChecked(True)
        self.assertEqual(w.plan.cost,14750)
        self.assertEqual(w.route_table.rowCount(),len(w.plan.steps))
        for box in w.target_boxes.values():
            box.setChecked(False)
        self.assertEqual(w.plan.status,"no_targets")
        w.mode.setCurrentIndex(w.mode.findData("Balanced"))
        self.assertTrue(w.weight_box.isVisible())

    def test_editor_corrects_door_observations_and_restrictions(self):
        w=self.win
        editor=StateEditor(w.session,w)
        editor.doors["stairs"].setCurrentIndex(2)
        editor.doors["lower_door"].setCurrentIndex(2)
        editor.apply_changes()
        w.refresh()
        self.assertEqual(w.plan.status,"unreachable")
        w.undo_button.click()
        self.assertEqual(w.plan.status,"found")
        editor=StateEditor(w.session,w)
        editor.zone.setCurrentIndex(editor.zone.findData("stage"))
        editor.flags["power"].setChecked(True)
        editor.points.setValue(2500)
        editor.apply_changes()
        w.refresh()
        self.assertEqual(w.plan.cost,2500)
        self.assertFalse(w.session.match.world.opened)
        self.assertEqual(w.zone.currentData(),"stage")
        self.assertEqual(w.route_table.rowCount(),2)

    def test_editor_rejects_conflict(self):
        w=self.win
        editor=StateEditor(w.session,w)
        editor.flags["jug"].setChecked(True)
        editor.apply_changes()
        self.assertIn("power",editor.problem.text())
        self.assertEqual(w.session.match,w.profile.initial)

    def test_confirm_full_setup_in_window(self):
        w=self.win
        w.points.setValue(14750)
        for check in w.target_boxes.values():
            check.setChecked(True)
        for _ in range(25):
            if not w.plan.steps:
                break
            self.assertTrue(w.confirm_button.isEnabled())
            w.confirm_button.click()
        self.assertEqual(w.plan.status,"complete")
        self.assertEqual(w.points.value(),0)
        self.assertTrue(set(w.profile.goals) <= w.session.match.world.flags)

    def test_switch_map_keeps_sessions_goals_and_history_separate(self):
        w = self.win
        w.points.setValue(3250)
        w.target_boxes["speed"].setChecked(True)
        w.confirm_button.click()
        kino_match = w.session.match
        kino_history = tuple(w.session.history)
        w.map_selector.setCurrentIndex(w.map_selector.findText("Die Maschine"))
        self.assertEqual(w.zone.currentData(), "yard")
        self.assertEqual(w.points.value(), 500)
        self.assertFalse(w.session.history)
        self.assertIn("Yard", w.history.item(0).text())
        w.confirm_button.click()
        cw_match = w.session.match
        w.map_selector.setCurrentIndex(w.map_selector.findText("Kino der Toten"))
        self.assertEqual(w.session.match, kino_match)
        self.assertEqual(tuple(w.session.history), kino_history)
        self.assertTrue(w.target_boxes["speed"].isChecked())
        w.map_selector.setCurrentIndex(w.map_selector.findText("Die Maschine"))
        self.assertEqual(w.session.match, cw_match)
        w.undo_button.click()
        self.assertEqual(w.zone.currentData(), "yard")

    def test_cold_war_marker_reveal_and_full_window_route(self):
        w = self.win
        w.map_selector.setCurrentIndex(w.map_selector.findText("Die Maschine"))
        w.points.setValue(30000)
        for box in w.target_boxes.values():
            box.setChecked(True)
        self.assertTrue(w.plan.to_marker)
        for _ in range(30):
            if not w.plan.steps:
                break
            w.confirm_button.click()
        self.assertEqual(w.plan.status, "marker_required")
        self.assertFalse(w.confirm_button.isEnabled())
        w.marker.setCurrentIndex(w.marker.findData("marker_pond"))
        self.assertFalse(w.plan.to_marker)
        self.assertTrue(any(step.id == "pond_tube" for step in w.plan.steps))
        for _ in range(40):
            if not w.plan.steps:
                break
            self.assertTrue(w.confirm_button.isEnabled())
            w.confirm_button.click()
        self.assertEqual(w.plan.status, "complete")

    def test_cold_war_editor_counts_existing_perks(self):
        w = self.win
        w.map_selector.setCurrentIndex(w.map_selector.findText("Die Maschine"))
        e = StateEditor(w.session, w)
        self.assertIsNone(e.cooldown)
        e.other_perks.setValue(2)
        e.zone.setCurrentIndex(e.zone.findData("medical"))
        e.flags["power"].setChecked(True)
        e.flags["jug"].setChecked(True)
        e.apply_changes()
        w.refresh()
        w.target_boxes["speed"].setChecked(True)
        self.assertEqual(w.plan.cost, 4000)
        self.assertEqual(w.target_prices["speed"].text(), "4,000 pts")
