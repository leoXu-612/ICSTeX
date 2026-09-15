"""Counterexamples for native-probe receipts; these are not native IME tests."""
from copy import deepcopy
from unittest import TestCase

from tools.probe_workbench_composition import observations_pass


class WorkbenchCompositionEvidenceTests(TestCase):
    def report(self, kind="ordinary"):
        original, expected = "base ", "base \u4e2d\u6587"

        def state(text, event_count, *, preedit=False, save=0, apply=0):
            value = {"text": text, "event_count": event_count, "preedit": preedit,
                     "files_unchanged": save == 0, "actions": {"save": save, "apply": apply},
                     "focus": "QLineEdit" if kind == "table" else "LaTeXEditor"}
            if kind != "ordinary":
                value.update(model=expected if apply else original, compile_created=False,
                             drafts=[] if apply or text == original else [[kind, "target"]])
            return value

        states = [state(original, 0), state(original, 1, preedit=True),
                  state(expected, 2), state(original, 2), state(expected, 2),
                  state(expected, 3, preedit=True), state(expected, 4)]
        applied = int(kind != "ordinary")
        if applied:
            states.append(state(expected, 4, apply=1))
        states.append(state(expected, 4, save=1, apply=applied))
        return {"kind": kind, "original": original, "expected": expected, "saved": expected,
                "events": [{"preedit": "zhong wen", "commit": ""},
                           {"preedit": "", "commit": "\u4e2d\u6587"},
                           {"preedit": "ni", "commit": ""}, {"preedit": "", "commit": ""}],
                "states": states, "actions": {"save": 1, "apply": applied},
                "other_table_preserved": True, "window_destroyed": True, "timeout": False,
                "app_sha256": "same-source", "app_sha256_after": "same-source"}

    def test_complete_ordinary_inspector_and_table_observations_pass(self):
        for kind in ("ordinary", "inspector", "table"):
            with self.subTest(kind=kind):
                self.assertTrue(observations_pass(self.report(kind)))

    def test_repeated_expected_states_before_undo_are_not_redo(self):
        report = self.report()
        states = report["states"]
        report["states"] = [states[0], states[1], states[2], deepcopy(states[2]), states[3]]
        self.assertFalse(observations_pass(report))

    def test_commit_without_a_second_cancelled_candidate_is_incomplete(self):
        report = self.report()
        report["events"] = report["events"][:2]
        self.assertFalse(observations_pass(report))

    def test_cancelling_candidate_must_leave_committed_text_unchanged(self):
        report = self.report()
        report["states"][-2]["text"] += "n"
        self.assertFalse(observations_pass(report))

    def test_preedit_must_not_enter_source(self):
        report = self.report()
        report["states"][1]["text"] += "zhong wen"
        self.assertFalse(observations_pass(report))

    def test_observed_source_write_before_explicit_save_refuses(self):
        report = self.report()
        report["states"][2]["files_unchanged"] = False
        self.assertFalse(observations_pass(report))

    def test_observed_block_model_change_before_apply_refuses(self):
        report = self.report("inspector")
        report["states"][2]["model"] = report["expected"]
        self.assertFalse(observations_pass(report))

    def test_observed_block_disk_change_before_apply_refuses(self):
        report = self.report("table")
        report["states"][2]["files_unchanged"] = False
        self.assertFalse(observations_pass(report))

    def test_missing_explicit_block_apply_refuses(self):
        report = self.report("table")
        report["actions"]["apply"] = 0
        self.assertFalse(observations_pass(report))

    def test_unrequested_block_compile_refuses(self):
        report = self.report("table")
        report["states"][-1]["compile_created"] = True
        self.assertFalse(observations_pass(report))

    def test_terminal_save_bytes_and_source_identity_remain_required(self):
        for key, value in (("window_destroyed", False), ("timeout", True),
                           ("saved", "wrong"), ("other_table_preserved", False),
                           ("app_sha256_after", "changed"), ("actions", {"save": 0, "apply": 0})):
            with self.subTest(key=key):
                report = self.report()
                report[key] = value
                self.assertFalse(observations_pass(report))
