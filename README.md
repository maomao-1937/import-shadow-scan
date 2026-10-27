# import-shadow-scan

[![tests](https://github.com/maomao-1937/import-shadow-scan/actions/workflows/tests.yml/badge.svg)](https://github.com/maomao-1937/import-shadow-scan/actions/workflows/tests.yml)

Inventory potential Python standard-library shadows and duplicate local names across **explicitly ordered import roots**, without opening or importing candidate source files. Python 3.11+; standard library only; no installation required.

Use this when reviewing source and generated directories together and you want a small, bounded filename inventory. For general linting, start with [Ruff A005](https://docs.astral.sh/ruff/rules/stdlib-module-shadowing/). This project does not claim a new discovery or predict runtime import resolution.

## Quickstart

Run these commands from a copy of this source directory:

```console
python import_shadow_scan.py --help
python import_shadow_scan.py . --format json
python -I import_shadow_scan.py . --format json
python examples/demo.py harmless
python examples/demo.py stdlib --format json
python examples/demo.py duplicate
python examples/demo.py namespace --format json
python examples/demo.py builtin
python -m unittest discover -s tests -v
```

The stdlib and duplicate examples intentionally exit **1**. Each demo creates its fixture in a temporary directory inside this project and removes it afterward; it never writes into your source roots. The scanner itself writes only to stdout/stderr. [中文快速开始](QUICKSTART.zh-CN.md).

## Command and exit codes

`python import_shadow_scan.py ROOT [ROOT ...] [--format json|text]`

Supply ordinary directories in the order you want inventoried. Paths with spaces must be quoted. The default format is text. JSON includes the executing Python version and reference scope, ordered roots, configured limits, ignored-name counts, candidates, findings, and information records. Candidate records contain `name`, absolute `path`, zero-based `root_index`, and `kind`. There are no source snippets. Text strings and JSON use ASCII escapes, including control characters in paths and diagnostics.

| Code | Meaning |
| --- | --- |
| 0 | No potential stdlib shadows or local concrete duplicates; information may exist |
| 1 | At least one potential stdlib shadow or local concrete duplicate |
| 2 | Invalid setup, unsupported link/reparse point, a bound exceeded, filesystem I/O failure, or output failure |

An error emits a diagnostic to stderr, with no partial inventory on stdout. A closed downstream stdout pipe returns 2, including for `--help`; output is flushed explicitly to avoid Python's shutdown exit 120.

## What is inventoried

Only each root's **immediate entries** are inspected. A regular file named `identifier.py` becomes a `module`; an identifier directory with an ordinary `__init__.py` becomes a `regular_package`; an identifier directory without that file becomes a `namespace_candidate`. Identifiers use Python's `str.isidentifier()` exactly, including Unicode and keyword spellings. Non-identifier `.py` stems and directory names increment `ignored.non_identifier`; other entries increment `ignored.other`. No directory recursion occurs, apart from checking the initializer's metadata.

For each name, concrete candidates retain root order. A package is listed before a same-name `.py` module **within the same root**. This is a lexical review order, not a claim about the actual runtime winner. Namespaces do not supersede concrete candidates in later roots. Repeated namespace-only names and namespace/concrete combinations are information; a namespace alone cannot create a duplicate or stdlib finding.

Concrete names present in the executing interpreter's `sys.stdlib_module_names` produce `potential_stdlib_shadow` findings, except names in `sys.builtin_module_names`: these produce `builtin_exemption` information because the built-in importer usually wins. Two or more concrete candidates produce a `local_duplicate` finding, including duplicate built-in names. One name can have both finding kinds. Matching is exact, with no case folding or Unicode normalization.

## Boundaries and filesystem assumptions

- At most 32 roots, 10,000 immediate entries per root (including ignored entries), and 50,000 total candidates (including namespaces). Exceeding a limit aborts rather than truncates the report.
- Duplicate resolved roots are rejected. Roots and every supplied root component must be ordinary directories. Candidate files/directories and package initializers must not be symlinks or Windows reparse points; these are refused, never followed. Non-regular initializers are also refused.
- Assume the filesystem is **immutable and non-adversarial during a scan**. Metadata checks are not an atomic, race-proof sandbox. In particular, do not scan paths another process can maliciously replace between checks.
- The inventory code never opens, reads, parses, deliberately imports, or executes candidate source contents, and never changes `sys.path`. **Python startup and the scanner's own standard-library imports remain trusted.** Existing `PYTHONPATH`, site hooks, or a root overlapping the scanner's installation/startup paths can affect that earlier startup phase. The inventory guarantee is not an absolute promise that no scanned code can ever run during interpreter startup.
- For a less exposed launch from anywhere, use `python -I <absolute-path-to-scanner> ROOT ...`: isolated mode excludes the current/script directory and `PYTHONPATH` from the interpreter's ordinary search setup. The executable source-directory command above also demonstrates `-I`. This is not a sandbox: use a trusted Python installation, scanner copy, and environment; site configuration is still trusted.
- The stdlib reference includes platform-specific modules unavailable on this machine. The report records the current interpreter; it does not model another Python environment.
- Frozen modules, extension modules, `.pyc`, `.pth`, ZIP imports, site hooks, `sys.modules`, case-insensitive filesystem resolution, custom importers and custom `meta_path` are not resolved. No installed-environment availability, exploitability, import failure, adoption, or frequency is inferred from a filename.

## Development

```console
python -m unittest discover -s tests -v
```

`checks.json` is a list of `{ "args": [...], "exit": N }` records. Run each argument list after prepending the current Python executable, from this directory. It includes expected 0/1/2 outcomes. See [TESTING.md](TESTING.md) for actual evidence and skips, and [RESEARCH.md](RESEARCH.md) for the motivation and alternatives. License: MIT.
