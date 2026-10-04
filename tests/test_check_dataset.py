"""Synthetic, temporary fixtures; no model imports or historical-data edits."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import check_dataset as checker


class DatasetAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "mydata"
        self.root.mkdir()
        (self.root / "synsetoffset2category.txt").write_text("canopy 02691156\n", encoding="utf-8")
        (self.root / "train_test_split").mkdir()
        for split in checker.SPLITS:
            stem = "sample_" + split
            self.pair(stem)
            self.split(split, [f"mydata/02691156/{stem}"])

    def cloud(self, stem="sample_train", folder="points", text="0 1 2\n3 4 5\n", category="02691156"):
        path = self.root / category / folder / (stem + ".pts")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def pair(self, stem, category="02691156"):
        return [self.cloud(stem, folder, category=category) for folder in ("points", "point_fake")]

    def split(self, name, value):
        path = self.root / "train_test_split" / f"shuffled_{name}_file_list.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def assert_issue(self, text):
        result = checker.check_dataset(self.root)
        self.assertFalse(result.ok)
        self.assertTrue(any(text in issue for issue in result.issues), result.issues)
        return result

    def test_valid_dataset_and_counts(self):
        result = checker.check_dataset(self.root)
        self.assertTrue(result.ok, result.issues)
        self.assertEqual(result.stats["pairs"], 3)
        self.assertEqual(result.stats["input_point_range"], [2, 2])
        self.assertEqual(result.stats["split_entries"], {"train": 1, "val": 1, "test": 1})
        self.assertEqual(result.stats["split_overlap"]["train/val"], 0)

    def test_missing_pair_in_either_direction(self):
        for folder in ("points", "point_fake"):
            with self.subTest(folder=folder):
                path = self.cloud(folder=folder)
                path.unlink()
                self.assert_issue("Unpaired cloud")
                self.cloud(folder=folder)

    def test_empty_cloud(self):
        path = self.cloud(text="\n \t\n")
        result = checker.check_cloud(path)
        self.assertFalse(result.ok)
        self.assertEqual(result.stats["points"], 0)

    def test_header_and_wrong_column_count(self):
        for text, message in (("X Y Z\n", "numeric"), ("2\n0 1 2\n", "exactly 3"),
                              ("0 1\n", "exactly 3"), ("0 1 2 3\n", "exactly 3")):
            with self.subTest(text=text):
                self.cloud(text=text)
                self.assert_issue(message)

    def test_nonfinite_and_float32_overflow(self):
        for coordinate in ("nan", "inf", "-inf", "1e999", "1e39"):
            with self.subTest(coordinate=coordinate):
                self.cloud(text=f"0 {coordinate} 2\n")
                self.assert_issue("finite")

    def test_whitespace_and_finite_exponents(self):
        path = self.cloud(text="  1e-3\t2.5  -3\n\n4 5 6\n")
        self.assertTrue(checker.check_cloud(path).ok)

    def test_dataset_rejects_one_row_input_and_target_even_with_minimum_one(self):
        for folder in ("points", "point_fake"):
            with self.subTest(folder=folder):
                self.cloud(folder=folder, text="0 1 2\n")
                result = checker.check_dataset(self.root, min_input_points=1, min_target_points=1)
                self.assertFalse(result.ok)
                self.assertTrue(any("at least 2 required" in issue for issue in result.issues), result.issues)
                self.cloud(folder=folder)

    def test_cloud_format_mode_accepts_one_row(self):
        path = self.cloud(text="0 1 2\n")
        self.assertTrue(checker.check_cloud(path).ok)
        with contextlib.redirect_stdout(io.StringIO()):
            code = checker.main(["--cloud", str(path)])
        self.assertEqual(code, 0)

    def test_python_specific_and_non_ascii_numeric_literals_are_rejected(self):
        for value in ("1_0", "\u0661\u0662", "\uff11\uff12", "0x10", "\u22121"):
            with self.subTest(value=value):
                self.cloud(text=f"{value} 1 2\n0 1 2\n")
                self.assert_issue("finite ASCII numeric literals")

    def test_cloud_byte_order_mark_is_not_silently_removed(self):
        path = self.cloud(text="0 1 2\n3 4 5\n")
        path.write_text("0 1 2\n3 4 5\n", encoding="utf-8-sig")
        self.assert_issue("no header or BOM")

    def test_split_byte_order_mark_is_rejected(self):
        path = self.split("train", ["mydata/02691156/sample_train"])
        path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
        self.assert_issue("BOM")

    def test_mapping_byte_order_mark_is_rejected(self):
        path = self.root / "synsetoffset2category.txt"
        path.write_text("canopy 02691156\n", encoding="utf-8-sig")
        self.assert_issue("must not contain a UTF-8 BOM")

    def test_supported_ascii_decimal_and_scientific_literals(self):
        for value in ("0", "-0", "+1", "1.", ".5", "-.5", "+.5", "1e3", "1.E-3", "-2.5e+2"):
            with self.subTest(value=value):
                path = self.cloud(text=f"{value} 1 2\n0 1 2\n")
                self.assertTrue(checker.check_cloud(path).ok)

    def test_optional_minimum_counts(self):
        result = checker.check_dataset(self.root, min_input_points=3, min_target_points=4)
        self.assertFalse(result.ok)
        self.assertEqual(sum("at least 3 required" in issue for issue in result.issues), 3)
        self.assertEqual(sum("at least 4 required" in issue for issue in result.issues), 3)

    def test_missing_mapping(self):
        (self.root / "synsetoffset2category.txt").unlink()
        self.assert_issue("Cannot read category mapping")

    def test_duplicate_and_unsafe_mapping(self):
        path = self.root / "synsetoffset2category.txt"
        for text, issue in (("canopy 02691156\nother 02691156\n", "duplicate category"),
                            ("canopy ../outside\n", "safe directory"),
                            ("canopy C:\\outside\n", "safe directory"),
                            ("canopy 02691156\n\n", "safe directory")):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                self.assert_issue(issue)

    def test_missing_split_file(self):
        self.split("val", []).unlink()
        self.assert_issue("Cannot read val split JSON")

    def test_malformed_split_json(self):
        self.split("val", []).write_text('["unterminated', encoding="utf-8")
        self.assert_issue("Cannot read val split JSON")

    def test_split_schema(self):
        for value, issue in (({"id": "sample_val"}, "list of strings"), ([123], "must be a string")):
            with self.subTest(value=value):
                self.split("val", value)
                self.assert_issue(issue)

    def test_unsafe_and_malformed_split_paths(self):
        entries = ("../02691156/sample_train", "mydata/../sample_train", "mydata/02691156/..",
                   "/02691156/sample_train", "C:/02691156/sample_train", r"mydata\02691156\sample_train",
                   "mydata/02691156/sample_train.pts", "mydata/02691156/sample_train.",
                   "mydata/02691156/sample_train/extra", "mydata/02691156/sample_train:stream",
                   "mydata//sample_train", "mydata/02691156/sample_train ")
        for entry in entries:
            with self.subTest(entry=entry):
                self.split("train", [entry])
                self.assert_issue("unsafe or malformed split ID")

    def test_unknown_category_and_missing_reference(self):
        for entry, issue in (("mydata/other/sample_train", "unknown category"),
                             ("mydata/02691156/missing", "no complete, exactly named cloud pair"),
                             ("mydata/02691156/SAMPLE_TRAIN", "no complete, exactly named cloud pair")):
            with self.subTest(entry=entry):
                self.split("train", [entry])
                self.assert_issue(issue)

    def test_duplicate_split_ids_and_prefix_aliases(self):
        for entry in ("mydata/02691156/sample_train", "renamed/02691156/sample_train"):
            with self.subTest(entry=entry):
                self.split("train", ["mydata/02691156/sample_train", entry])
                self.assert_issue("duplicate split ID or prefix/category alias")

    def test_cross_split_overlap_is_a_failure(self):
        self.split("val", ["mydata/02691156/sample_val", "alias/02691156/sample_train"])
        result = self.assert_issue("Split leakage: train/val overlap on 1 ID")
        self.assertEqual(result.stats["split_overlap"]["train/val"], 1)

    def test_cross_category_stems_are_ambiguous_for_legacy_loader(self):
        with (self.root / "synsetoffset2category.txt").open("a", encoding="utf-8") as handle:
            handle.write("other 12345678\n")
        self.pair("sample_train", category="12345678")
        self.assert_issue("the legacy loader matches IDs globally")

    def test_unassigned_pairs(self):
        self.pair("unassigned")
        result = self.assert_issue("absent from all splits")
        self.assertEqual(result.stats["unassigned_pairs"], 1)

    def test_canonical_cloud_alias_is_a_duplicate(self):
        original = self.cloud().resolve()
        self.cloud("alias")
        original_resolve = Path.resolve

        def resolve_alias(path, *args, **kwargs):
            if path.name == "alias.pts":
                return original
            return original_resolve(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", new=resolve_alias):
            self.assert_issue("Duplicate cloud ID or file alias")

    def test_symlink_cannot_escape_dataset_root(self):
        outside = self.root.parent / "outside.pts"
        outside.write_text("0 1 2\n", encoding="utf-8")
        path = self.cloud()
        path.unlink()
        try:
            path.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Platform cannot create symlinks: {exc}")
        self.assert_issue("Unsafe path outside dataset root")

    def test_cli_modes_exit_codes_and_json(self):
        script = str(Path(checker.__file__).resolve())
        process = subprocess.run([sys.executable, script, "--root", str(self.root), "--json"],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "PASS")
        self.split("val", ["mydata/02691156/sample_train"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = checker.main(["--root", str(self.root), "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "FAIL")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = checker.main(["--cloud", str(self.cloud()), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "cloud-format-only")
        with contextlib.redirect_stderr(io.StringIO()):
            code = checker.main(["--root", str(self.root / "missing")])
        self.assertEqual(code, 2)

    def test_cloud_check_never_changes_file_contents(self):
        path = self.cloud()
        before = path.read_bytes()
        checker.check_cloud(path)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
