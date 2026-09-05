#!/usr/bin/env python3
"""CPU-only behavior and fail-closed tests for the hybrid APC overlay."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
PATCH = next(
    p for p in (
        HERE / "patch_hybrid_prefix_hit.py",
        HERE.parent / "overlay" / "patch_hybrid_prefix_hit.py",
    ) if p.is_file()
)
SPEC = importlib.util.spec_from_file_location("hybrid_patch", PATCH)
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def fixture() -> str:
    return (
        "def _validate_prefix_cache_retention_interval(\n):\n    pass\n\n"
        "class Coordinator:\n"
        "    def __init__(self):\n"
        + patch.EAGLE_OLD
        + "        if True:\n"
        + patch.FINE_OLD
        + "    def verify(self):\n"
        + patch.LOG_OLD
        + "    def lookup(self):\n"
        + "        while True:\n            for spec in ():\n"
        + patch.MIN_OLD
    )


def manager(name: str, supported: bool, block_size: int = 3584):
    return type(name, (), {
        "supports_fine_grained_hash_lookup": supported,
        "block_size": block_size,
    })()


def group(participates):
    return SimpleNamespace(kv_cache_spec=SimpleNamespace(
        participates_in_prefix_caching=participates,
    ))


def unsupported(managers, groups):
    namespace = {
        "self": SimpleNamespace(single_type_managers=managers),
        "kv_cache_config": SimpleNamespace(kv_cache_groups=groups),
        "hash_block_size": 64,
    }
    exec(textwrap.dedent(patch.FINE_NEW), namespace)
    return namespace["unsupported_partial_hit_managers"]


class EligibilityTest(unittest.TestCase):
    def test_transient_tail_does_not_veto_supported_reusable_managers(self):
        managers = [manager("MLAManager", True), manager("MambaManager", True),
                    manager("KpoolTailManager", False)]
        self.assertEqual(unsupported(managers, [group(True), group(True), group(False)]), set())

    def test_each_unsupported_reusable_manager_still_vetoes_partial_hits(self):
        for name in ("MLAManager", "MambaManager", "SlidingWindowManager"):
            with self.subTest(name=name):
                self.assertEqual(unsupported([manager(name, False)], [group(True)]), {name})

    def test_native_hash_sized_manager_needs_no_partial_support(self):
        self.assertEqual(unsupported([manager("NativeManager", False, 64)], [group(True)]), set())

    def test_only_explicit_false_opts_out(self):
        for value in (None, 0, "", "false", True):
            with self.subTest(value=value):
                self.assertEqual(unsupported([manager("UnknownManager", False)], [group(value)]),
                                 {"UnknownManager"})

    def test_missing_participation_metadata_fails_closed(self):
        with self.assertRaises(AttributeError):
            unsupported([manager("UnknownManager", False)], [SimpleNamespace(kv_cache_spec=object())])

    def test_misaligned_manager_and_group_lists_fail_closed(self):
        for managers, groups in (([manager("Unknown", False)], []), ([], [group(True)])):
            with self.subTest(managers=managers, groups=groups), self.assertRaises(ValueError):
                unsupported(managers, groups)


class HybridMinimumTest(unittest.TestCase):
    def run_minimum(self, name, proposed):
        namespace = {
            "spec": type(name, (), {})(), "drop_eagle_block": False,
            "eagle_verified": set(), "idx": 0, "_new_hit_length": proposed,
            "curr_hit_length": 640, "group_ids": [0], "hit_blocks": [["cached"]],
            "hit_blocks_by_group": {0: []}, "hit_length_by_group": {0: 0},
            "longest_hit_length": 0,
        }
        exec(patch.HELPER, namespace)
        exec("for _iteration in (0,):\n" + textwrap.indent(textwrap.dedent(patch.MIN_NEW), "    "),
             namespace)
        return namespace

    def test_mamba_miss_and_mla_shorter_hit_constrain_minimum(self):
        for name, proposed in (("MambaSpec", 0), ("MLAAttentionSpec", 128)):
            with self.subTest(name=name):
                result = self.run_minimum(name, proposed)
                self.assertEqual(result["curr_hit_length"], proposed)
                self.assertEqual(result["hit_length_by_group"][0], proposed)

    def test_drafter_miss_allocates_fresh_window_without_lowering_target_hit(self):
        result = self.run_minimum("SlidingWindowSpec", 0)
        self.assertEqual(result["curr_hit_length"], 640)
        self.assertEqual(result["hit_blocks_by_group"][0], [])

    def test_tail_is_never_classified_as_drafter(self):
        namespace = {}
        exec(patch.HELPER, namespace)
        self.assertFalse(namespace["_glm53_is_draft_swa_spec"](type("KpoolTailSpec", (), {})()))


class PatcherSafetyTest(unittest.TestCase):
    def apply(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kv_cache_coordinator.py"
            target.write_text(source, encoding="utf-8")
            original = patch.P
            patch.P = target
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    patch.main()
                return target.read_text(encoding="utf-8")
            finally:
                patch.P = original

    def assert_rejected_without_write(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "kv_cache_coordinator.py"
            target.write_text(source, encoding="utf-8")
            original = patch.P
            patch.P = target
            try:
                before = target.read_bytes()
                with self.assertRaises((SystemExit, SyntaxError)):
                    patch.main()
                self.assertEqual(target.read_bytes(), before)
            finally:
                patch.P = original

    def test_fresh_install_and_exact_idempotence(self):
        installed = self.apply(fixture())
        self.assertEqual(self.apply(installed), installed)
        compile(installed, "fixture", "exec")

    def test_additive_install_over_old_hybrid_overlay(self):
        installed = self.apply(fixture())
        legacy = installed.replace(patch.FINE_NEW, patch.FINE_OLD)
        self.assertEqual(self.apply(legacy), installed)

    def test_missing_duplicate_and_drifted_source_anchors_do_not_write(self):
        for source in (
            fixture().replace(patch.FINE_OLD, "            pass\n"),
            fixture().replace(patch.FINE_OLD, patch.FINE_OLD * 2),
            fixture().replace("if use_eagle and", "if unknown_eagle and"),
        ):
            with self.subTest(source=source[-80:]):
                self.assert_rejected_without_write(source)

    def test_marker_with_damaged_patch_is_rejected(self):
        installed = self.apply(fixture())
        for source in (
            installed.replace("swa_ids or set(", "unsafe_ids or set("),
            installed.replace(" is not False", " is True"),
            fixture() + "\n" + patch.MARK + "\n" + patch.FINE_MARK + "\n",
        ):
            with self.subTest(source=source[-80:]):
                self.assert_rejected_without_write(source)

    def test_invalid_generated_python_is_rejected_without_write(self):
        self.assert_rejected_without_write(fixture() + "\nsyntax error here\n")


if __name__ == "__main__":
    unittest.main()
