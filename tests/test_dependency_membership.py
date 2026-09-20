from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.dependency_membership import MembershipInputs, calculate_memberships
from app.core.project_dependencies import observe_input


class MembershipCalculationTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.scope = Path(self.temporary.name).resolve()
        self.root = self.scope / "main.tex"
        self.child = self.scope / "child.tex"
        self.root.write_text("\\input{child.tex}")
        self.child.write_text("original")
        self.inputs = MembershipInputs(((1, self.root, self.root),), self.scope, (), (), (), (), frozenset())

    def test_snapshot_buffer_overrides_disk_without_mutation(self):
        missing = self.scope / "missing.tex"
        inputs = replace(self.inputs, buffers=((self.root, "\\input{missing.tex}"),))
        result = calculate_memberships(inputs, cancelled=lambda: False)
        self.assertEqual(result.roots[0].paths, frozenset({self.root, missing}))
        self.assertEqual(self.root.read_text(), "\\input{child.tex}")
        with self.assertRaises(FrozenInstanceError):
            result.roots[0].complete = False

    def test_new_paths_have_content_baselines_for_post_commit_recheck(self):
        result = calculate_memberships(self.inputs, cancelled=lambda: False)
        baseline = dict(result.initial_observations)[self.child]
        self.child.write_text("changed after calculation")
        self.assertNotEqual(baseline, observe_input(self.child, self.scope))

    def test_missing_and_substituted_paths_remain_observable_without_link_reads(self):
        missing = self.scope / "missing.tex"
        link = self.scope / "link.tex"
        link.symlink_to(self.child)
        inputs = replace(self.inputs, previous=((self.root, frozenset({missing, link})),))
        result = calculate_memberships(inputs, cancelled=lambda: False)
        self.assertTrue({missing, link}.issubset(result.roots[0].paths))
        self.assertFalse(dict(result.initial_observations)[link].readable)

    def test_recorded_extra_paths_are_scoped_and_shared_children_keep_each_root(self):
        other = self.scope / "other.tex"
        other.write_text("\\input{child.tex}")
        data = self.scope / "data.csv"
        data.write_text("x,y")
        inputs = replace(self.inputs, tabs=(*self.inputs.tabs, (2, other, other)),
            recorded=((self.root, frozenset({data, self.scope.parent / "outside.csv"})),))
        result = calculate_memberships(inputs, cancelled=lambda: False)
        self.assertEqual(len(result.roots), 2)
        self.assertTrue(all(self.child in row.paths for row in result.roots))
        self.assertFalse(any(self.scope.parent / "outside.csv" in row.paths for row in result.roots))
        self.assertIn(data, result.roots[0].paths)

    def test_cancel_never_returns_publishable_result(self):
        self.assertIsNone(calculate_memberships(self.inputs, cancelled=lambda: True))

    def test_child_changing_during_parse_does_not_publish_incomplete_graph(self):
        from app.core import dependency_membership
        original = dependency_membership.read_project_bytes

        def changing(path, scope):
            raw = original(path, scope)
            if path == self.child:
                self.child.write_text("\\input{new-grandchild.tex}")
            return raw

        with patch.object(dependency_membership, "read_project_bytes", side_effect=changing):
            self.assertIsNone(calculate_memberships(self.inputs, cancelled=lambda: False))

    def test_saved_buffer_comparison_preserves_encoding_and_qt_line_projection(self):
        text = "\u4e2d\u6587\r\nsecond line\rthird line"
        raw = text.encode("gbk")
        self.root.write_bytes(raw)
        inputs = replace(self.inputs, buffers=((self.root, "\u4e2d\u6587\nsecond line\nthird line"),),
                         saved_buffers=((self.root, "gbk"),))
        result = calculate_memberships(inputs, cancelled=lambda: False)
        self.assertFalse(result.changed_saved_buffers)
        self.assertEqual(self.root.read_bytes(), raw)

    def test_saved_buffer_mismatch_is_reported_not_applied_or_used_as_graph(self):
        inputs = replace(self.inputs, buffers=((self.root, "old saved content"),),
                         saved_buffers=((self.root, "utf-8"),))
        result = calculate_memberships(inputs, cancelled=lambda: False)
        self.assertEqual(result.changed_saved_buffers, (self.root,))
        self.assertFalse(result.roots)
