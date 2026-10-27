import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "import_shadow_scan.py"


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-tmp-", dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.a = self.base / "a"
        self.b = self.base / "b"
        self.a.mkdir()
        self.b.mkdir()

    def run_scan(self, *roots, extra=()):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, roots), *extra],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def report(self, *roots):
        result = self.run_scan(*roots, extra=("--format", "json"))
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result, json.loads(result.stdout)

    def module(self, root, name, source="raise RuntimeError('NEVER_EXECUTE')\n"):
        (root / (name + ".py")).write_text(source, encoding="utf-8")

    def package(self, root, name):
        package = root / name
        package.mkdir()
        (package / "__init__.py").write_text("raise RuntimeError('NEVER_EXECUTE')\n", encoding="utf-8")

    def load_scanner(self):
        spec = importlib.util.spec_from_file_location("scanner_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_harmless(self):
        self.module(self.a, "widget_local")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["candidates"][0]["kind"], "module")

    def test_stdlib_reference_and_json(self):
        self.module(self.a, "json")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["findings"][0]["kind"], "potential_stdlib_shadow")
        self.assertEqual(report["findings"][0]["name"], "json")
        self.assertEqual(report["reference"]["python_version"], sys.version.split()[0])
        self.assertIn("sys.stdlib_module_names", report["reference"]["stdlib_names"])

    def test_root_order_preserved(self):
        self.module(self.a, "widget_local")
        self.module(self.b, "widget_local")
        result, report = self.report(self.b, self.a)
        duplicate = report["findings"][0]
        self.assertEqual(result.returncode, 1)
        self.assertEqual(duplicate["kind"], "local_duplicate")
        self.assertEqual([c["root_index"] for c in duplicate["ordered_candidates"]], [0, 1])
        self.assertTrue(duplicate["ordered_candidates"][0]["path"].endswith("b" + os.sep + "widget_local.py"))

    def test_package_before_module_same_root(self):
        self.module(self.a, "widget_local")
        self.package(self.a, "widget_local")
        _, report = self.report(self.a)
        candidates = report["findings"][0]["ordered_candidates"]
        self.assertEqual([c["kind"] for c in candidates], ["regular_package", "module"])

    def test_namespace_does_not_hide_later_concrete(self):
        (self.a / "widget_local").mkdir()
        self.module(self.b, "widget_local")
        result, report = self.report(self.a, self.b)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["findings"], [])
        self.assertEqual([c["kind"] for c in report["candidates"]], ["namespace_candidate", "module"])
        self.assertEqual(report["information"][0]["kind"], "namespace_candidates")

    def test_namespace_only_repeats_are_information(self):
        (self.a / "json").mkdir()
        (self.b / "json").mkdir()
        result, report = self.report(self.a, self.b)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(report["information"][0]["candidates"]), 2)
        self.assertEqual(report["findings"], [])

    def test_builtin_exemption(self):
        self.module(self.a, "sys")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["information"][0]["kind"], "builtin_exemption")

    def test_builtin_still_reports_local_duplicate(self):
        self.module(self.a, "sys")
        self.module(self.b, "sys")
        result, report = self.report(self.a, self.b)
        self.assertEqual(result.returncode, 1)
        self.assertEqual([f["kind"] for f in report["findings"]], ["local_duplicate"])

    def test_duplicate_resolved_roots(self):
        result = self.run_scan(self.a, self.a / ".")
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate", result.stderr.lower())

    def test_missing_and_file_roots(self):
        self.module(self.a, "x")
        for root in (self.base / "missing", self.a / "x.py"):
            with self.subTest(root=root):
                result = self.run_scan(root)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")

    def test_invalid_names_and_nonrecursive_inventory(self):
        (self.a / "not-a-name.py").write_text("secret", encoding="utf-8")
        (self.a / "not-a-dir").mkdir()
        (self.a / "notes.txt").write_text("secret", encoding="utf-8")
        (self.a / "namespace_local").mkdir()
        self.module(self.a / "namespace_local", "json")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["ignored"]["non_identifier"], 2)
        self.assertEqual(report["ignored"]["other"], 1)
        self.assertEqual([c["name"] for c in report["candidates"]], ["namespace_local"])

    def test_source_not_read_parsed_or_executed(self):
        self.module(self.a, "widget_local", "raise RuntimeError('SECRET_SENTINEL')\ninvalid syntax !!!\n")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("SECRET_SENTINEL", result.stdout + result.stderr)
        scanner = self.load_scanner()
        original_open = __import__("builtins").open

        def guard(file, *args, **kwargs):
            if str(file).endswith("widget_local.py"):
                self.fail("candidate source opened")
            return original_open(file, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=guard), mock.patch("ast.parse", side_effect=AssertionError("AST parsed")):
            scanner.scan_roots([str(self.a)])

    def test_exception_raising_source_is_never_executed(self):
        self.module(self.a, "json", "raise RuntimeError('EXECUTION_WOULD_FAIL')\n")
        result, report = self.report(self.a)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("EXECUTION_WOULD_FAIL", result.stdout + result.stderr)

    def test_missing_arguments_and_escaped_errors(self):
        self.assertEqual(self.run_scan().returncode, 2)
        result = self.run_scan(self.a, extra=("--bad\x1b",))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("\x1b", result.stderr)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_real_windows_junction_rejected(self):
        link = self.base / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.a)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.addCleanup(lambda: os.rmdir(link))
        result = self.run_scan(link)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reparse", result.stderr)

    def test_help_closed_stdout_returns_two(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            process = subprocess.Popen([sys.executable, str(SCRIPT), "--help"], stdout=write_fd, stderr=subprocess.PIPE)
        finally:
            os.close(write_fd)
        _, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 2, stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"Exception ignored", stderr)

    def make_link(self, target, link, is_directory=False):
        try:
            link.symlink_to(target, target_is_directory=is_directory)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows WinError 1314: symlink creation privilege unavailable")
            raise

    def test_root_link_rejected(self):
        link = self.base / "linked_root"
        self.make_link(self.a, link, True)
        result = self.run_scan(link)
        self.assertEqual(result.returncode, 2)

    def test_root_ancestor_link_rejected(self):
        (self.a / "nested").mkdir()
        link = self.base / "linked_parent"
        self.make_link(self.a, link, True)
        self.assertEqual(self.run_scan(link / "nested").returncode, 2)

    def test_module_link_rejected(self):
        self.module(self.b, "target_local")
        self.make_link(self.b / "target_local.py", self.a / "json.py")
        self.assertEqual(self.run_scan(self.a).returncode, 2)

    def test_package_link_rejected(self):
        self.package(self.b, "target_local")
        self.make_link(self.b / "target_local", self.a / "json", True)
        self.assertEqual(self.run_scan(self.a).returncode, 2)

    def test_init_link_rejected(self):
        (self.a / "json").mkdir()
        self.module(self.b, "target_local")
        self.make_link(self.b / "target_local.py", self.a / "json" / "__init__.py")
        self.assertEqual(self.run_scan(self.a).returncode, 2)

    def test_reparse_attribute_recognized(self):
        scanner = self.load_scanner()
        self.assertTrue(scanner.is_link_or_reparse(type("Stat", (), {"st_mode": 0o100644, "st_file_attributes": 0x400})()))
        self.assertFalse(scanner.is_link_or_reparse(type("Stat", (), {"st_mode": 0o100644, "st_file_attributes": 0})()))

    def test_all_bounds(self):
        scanner = self.load_scanner()
        with self.assertRaisesRegex(scanner.ScanError, "32"):
            scanner.scan_roots([str(self.a)] * 33)
        self.module(self.a, "widget_local")
        self.module(self.a, "other_local")
        with mock.patch.object(scanner, "MAX_ENTRIES_PER_ROOT", 1):
            with self.assertRaisesRegex(scanner.ScanError, "entries"):
                scanner.scan_roots([str(self.a)])
        with mock.patch.object(scanner, "MAX_CANDIDATES", 1):
            with self.assertRaisesRegex(scanner.ScanError, "candidates"):
                scanner.scan_roots([str(self.a)])

    def test_io_error_is_setup_error(self):
        scanner = self.load_scanner()
        with mock.patch.object(scanner.os, "scandir", side_effect=PermissionError("access denied")):
            with self.assertRaises(scanner.ScanError):
                scanner.scan_roots([str(self.a)])

    def test_text_escapes_control_characters(self):
        if os.name == "nt":
            self.skipTest("Windows disallows control characters in path components")
        root = self.base / "escape\x1b[31m"
        root.mkdir()
        result = self.run_scan(root)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("\x1b", result.stdout + result.stderr)
        self.assertIn("\\u001b", result.stdout)

    def test_closed_stdout_returns_two_without_shutdown_120(self):
        self.module(self.a, "json")
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            process = subprocess.Popen([sys.executable, str(SCRIPT), str(self.a)], stdout=write_fd, stderr=subprocess.PIPE)
        finally:
            os.close(write_fd)
        _, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 2, stderr.decode("utf-8", "replace"))
        self.assertNotIn(b"Exception ignored", stderr)


if __name__ == "__main__":
    unittest.main()
