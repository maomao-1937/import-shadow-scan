"""Build an ephemeral example, invoke the scanner, then remove the example."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("harmless", "stdlib", "duplicate", "namespace", "builtin", "invalid", "raising"))
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix=".example-tmp-", dir=PROJECT) as temporary:
        first, second = Path(temporary) / "first", Path(temporary) / "second"
        first.mkdir()
        second.mkdir()
        roots = [first]
        if args.case == "harmless":
            (first / "widget_local.py").write_text("# example only\n", encoding="utf-8")
        elif args.case in ("stdlib", "raising"):
            (first / "json.py").write_text("raise RuntimeError('source must never run')\n", encoding="utf-8")
        elif args.case == "duplicate":
            (first / "widget_local.py").write_text("# first\n", encoding="utf-8")
            (second / "widget_local").mkdir()
            (second / "widget_local" / "__init__.py").write_text("# second\n", encoding="utf-8")
            roots.append(second)
        elif args.case == "namespace":
            (first / "widget_local").mkdir()
            (second / "widget_local.py").write_text("# concrete\n", encoding="utf-8")
            roots.append(second)
        elif args.case == "builtin":
            (first / "sys.py").write_text("# builtin exception\n", encoding="utf-8")
        elif args.case == "invalid":
            roots = [first / "missing"]
        return subprocess.call([sys.executable, str(PROJECT / "import_shadow_scan.py"),
                                *map(str, roots), "--format", args.format])


if __name__ == "__main__":
    raise SystemExit(main())
