"""Bounded filename inventory for explicitly ordered Python import roots."""

import argparse
import json
import os
from pathlib import Path
import stat
import sys


MAX_ROOTS = 32
MAX_ENTRIES_PER_ROOT = 10_000
MAX_CANDIDATES = 50_000


class ScanError(Exception):
    """Invalid setup, unsupported metadata, limit, or filesystem failure."""


def is_link_or_reparse(metadata):
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & 0x400
    )


def _root_path(raw):
    # Validate before resolve/abspath can erase an explicitly supplied link/.. .
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    for component in [*reversed(path.parents), path]:
        metadata = component.lstat()
        if is_link_or_reparse(metadata):
            raise ScanError(f"root component is a link or reparse point: {component}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ScanError(f"root component is not an ordinary directory: {component}")
    return path.resolve(strict=True)


def _inventory(root, root_index, candidates, ignored):
    entries = []
    with os.scandir(root) as iterator:
        for entry in iterator:
            if len(entries) >= MAX_ENTRIES_PER_ROOT:
                raise ScanError(f"root exceeds {MAX_ENTRIES_PER_ROOT} entries: {root}")
            entries.append(entry)
    for entry in sorted(entries, key=lambda item: item.name):
        name = entry.name
        path = root / name
        metadata = entry.stat(follow_symlinks=False)
        is_python_name = name.endswith(".py") and name[:-3].isidentifier()
        is_identifier = name.isidentifier()
        if is_link_or_reparse(metadata) and (is_python_name or is_identifier):
            raise ScanError(f"candidate is a link or reparse point: {path}")
        kind = None
        if stat.S_ISREG(metadata.st_mode) and name.endswith(".py"):
            if is_python_name:
                name, kind = name[:-3], "module"
            else:
                ignored["non_identifier"] += 1
        elif stat.S_ISDIR(metadata.st_mode):
            if not is_identifier:
                ignored["non_identifier"] += 1
            else:
                init_path = path / "__init__.py"
                try:
                    init_metadata = init_path.lstat()
                except FileNotFoundError:
                    kind = "namespace_candidate"
                else:
                    if is_link_or_reparse(init_metadata):
                        raise ScanError(f"package initializer is a link or reparse point: {init_path}")
                    if not stat.S_ISREG(init_metadata.st_mode):
                        raise ScanError(f"package initializer is not an ordinary file: {init_path}")
                    kind = "regular_package"
        else:
            ignored["other"] += 1
        if kind is not None:
            if len(candidates) >= MAX_CANDIDATES:
                raise ScanError(f"inventory exceeds {MAX_CANDIDATES} candidates")
            candidates.append({"name": name, "path": str(path), "root_index": root_index, "kind": kind})


def scan_roots(raw_roots):
    """Inspect names and metadata only; assume an immutable, non-adversarial tree."""
    if not 1 <= len(raw_roots) <= MAX_ROOTS:
        raise ScanError(f"supply between 1 and {MAX_ROOTS} roots")
    if not hasattr(sys, "stdlib_module_names"):
        raise ScanError("Python with sys.stdlib_module_names is required (Python 3.11+ supported)")
    roots, seen = [], set()
    candidates = []
    ignored = {"non_identifier": 0, "other": 0}
    try:
        for raw in raw_roots:
            root = _root_path(raw)
            identity = os.path.normcase(str(root))
            if identity in seen:
                raise ScanError(f"duplicate resolved root: {root}")
            seen.add(identity)
            roots.append(root)
        for index, root in enumerate(roots):
            _inventory(root, index, candidates, ignored)
    except (OSError, ValueError) as exc:
        raise ScanError(f"filesystem setup or I/O error: {exc}") from exc
    rank = {"regular_package": 0, "module": 1, "namespace_candidate": 2}
    candidates.sort(key=lambda c: (c["root_index"], c["name"], rank[c["kind"]], c["path"]))
    grouped = {}
    for candidate in candidates:
        grouped.setdefault(candidate["name"], []).append(candidate)
    findings, information = [], []
    builtin_names = set(sys.builtin_module_names)
    for name, group in sorted(grouped.items()):
        concrete = [c for c in group if c["kind"] != "namespace_candidate"]
        namespaces = [c for c in group if c["kind"] == "namespace_candidate"]
        if namespaces:
            information.append({"kind": "namespace_candidates", "name": name, "candidates": namespaces,
                                "note": "Namespace directories alone are not concrete duplicate or stdlib findings."})
        if concrete and name in builtin_names:
            information.append({"kind": "builtin_exemption", "name": name, "candidates": concrete,
                                "note": "The built-in importer usually wins; custom meta_path is outside scope."})
        elif concrete and name in sys.stdlib_module_names:
            findings.append({"kind": "potential_stdlib_shadow", "name": name, "ordered_candidates": concrete})
        if len(concrete) > 1:
            findings.append({"kind": "local_duplicate", "name": name, "ordered_candidates": concrete})
    return {
        "schema_version": 1,
        "reference": {
            "python_version": sys.version.split()[0],
            "python_implementation": sys.implementation.name,
            "stdlib_names": "sys.stdlib_module_names of the executing Python; includes unavailable platform modules",
            "builtin_names": "sys.builtin_module_names of the executing Python",
            "scope": "Immediate filenames in explicit ordered roots; lexical candidates, not runtime import resolution",
        },
        "roots": [str(root) for root in roots],
        "limits": {"roots": MAX_ROOTS, "entries_per_root": MAX_ENTRIES_PER_ROOT, "total_candidates": MAX_CANDIDATES},
        "ignored": ignored,
        "candidates": candidates,
        "findings": findings,
        "information": information,
    }


def _quoted(value):
    return json.dumps(value, ensure_ascii=True)


def render_text(report):
    lines = ["import-shadow-scan", "Python: " + _quoted(report["reference"]["python_version"]),
             "Scope: " + _quoted(report["reference"]["scope"]),
             "Stdlib reference: " + _quoted(report["reference"]["stdlib_names"]),
             "Builtin reference: " + _quoted(report["reference"]["builtin_names"])]
    for index, root in enumerate(report["roots"]):
        lines.append(f"Root {index}: {_quoted(root)}")
    for candidate in report["candidates"]:
        lines.append("Candidate: " + _quoted(candidate))
    for item in report["findings"]:
        lines.append("Finding: " + _quoted(item))
    for item in report["information"]:
        lines.append("Information: " + _quoted(item))
    lines.append("Ignored: " + _quoted(report["ignored"]))
    lines.append(f"Findings: {len(report['findings'])}")
    return "\n".join(lines)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ScanError(message)

    def exit(self, status=0, message=None):
        # argparse's help path exits before main's normal output flush.
        if message:
            sys.stderr.write(message)
        sys.stdout.flush()
        raise SystemExit(status)


def _silence_failed_stdout():
    # Explicit flush in main catches failure before Python's shutdown flush.
    # Replacing the descriptor also prevents shutdown from changing 2 to 120.
    try:
        descriptor = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(descriptor, sys.stdout.fileno())
        finally:
            os.close(descriptor)
    except (OSError, ValueError, AttributeError):
        sys.stdout = None


def main(argv=None):
    parser = _Parser(prog="import_shadow_scan.py", description=__doc__)
    parser.add_argument("roots", metavar="ROOT", nargs="+")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    try:
        args = parser.parse_args(argv)
        report = scan_roots(args.roots)
        output = json.dumps(report, ensure_ascii=True, indent=2) if args.format == "json" else render_text(report)
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        return 1 if report["findings"] else 0
    except ScanError as exc:
        try:
            sys.stderr.write("import-shadow-scan: " + _quoted(str(exc)) + "\n")
            sys.stderr.flush()
        except OSError:
            pass
        return 2
    except (OSError, UnicodeError):
        _silence_failed_stdout()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
