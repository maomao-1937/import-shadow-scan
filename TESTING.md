# Testing evidence

Local verification date: 2026-10-27 (Asia/Singapore). Environment: CPython 3.11.15, MSC v.1944 64-bit AMD64, Windows-10-10.0.26300-SP0. Shell command `python` resolved to `D:\Hermes\hermes-agent\venv\Scripts\python.exe`. No third-party Python packages are required by the project.

## Observed RED, then GREEN

Tests were written before the inventory implementation. The initial missing-file run was scaffolding feedback, not the semantic RED evidence. A minimal empty-report scaffold was then used for a meaningful failing assertion:

```console
python -m unittest discover -s tests -p test_scan.py -k stdlib_reference -v
```

Observed: **1 test failed**, `AssertionError: 0 != 1`. A real `json.py` candidate incorrectly produced exit 0 before shadow findings were implemented. After implementation, the first full suite passed 22 tests with 6 skips.

An additional test caught a separate real output defect:

```console
python -m unittest discover -s tests -p test_scan.py -k help_closed -v
```

Observed RED: **1 test failed**, `AssertionError: 120 != 2`, with `Exception ignored` / `OSError: [Errno 22] Invalid argument` during the stdout shutdown flush. After explicitly flushing argparse's help exit path and redirecting a failed stdout descriptor to the null device, both report-output and help-output real closed-pipe tests return 2.

Final full-suite command:

```console
python -m unittest discover -s tests -v
```

Observed: **26 tests run; 20 passed, 6 skipped; 0 failures and 0 errors**. The suite checks root order, same-root package/module ties, namespace/concrete combinations, namespace repeats, built-in exceptions and duplicates, stdlib JSON metadata, harmless modules, duplicate roots, invalid roots and names, nonrecursive traversal, invalid-syntax and exception-raising candidate sources, guarded candidate content access, actual filesystem I/O failure handling, all three bounds, diagnostic escaping, a reparse-attribute predicate, and real closed stdout pipes.

The six local skips are explicit:

- Five symlink creation cases (root, ancestor, module, package directory, initializer): Windows returned **WinError 1314**, meaning required symlink privilege is unavailable. These are skips, not successful link-refusal tests.
- The path containing an ESC character: Windows forbids such path components. Diagnostic escaping is still exercised with an invalid option containing ESC.

A **real Windows directory junction** was created without elevated privileges and passed the root reparse-refusal test. The junction was removed afterward. The metadata predicate is also tested with a synthetic Windows reparse attribute; this does not establish behavior for every native reparse type. On non-Windows systems the native junction test skips; symlink/control-character cases run when supported. No Linux/macOS result is claimed here.

## Executable command checks

`checks.json` contains 11 independent argument lists with expected exits 0, 1, and 2. They were executed from the project directory with the current `sys.executable` prepended. Observed: **11/11 matched expected exit codes**, including an isolated `-I` launch, stdlib and local duplicate findings, namespace and built-in information, invalid setup, and exception-raising source.

This portable check command can be copied into a shell from the source directory:

```console
python -c "import json,subprocess,sys; cases=json.load(open('checks.json',encoding='utf-8')); results=[(case,subprocess.run([sys.executable,*case['args']],capture_output=True).returncode) for case in cases]; [print(case['args'],code,'expected',case['exit']) for case,code in results]; sys.exit(any(code!=case['exit'] for case,code in results))"
```

These are local checks. They do not establish actual application import resolution, deployment integration, adoption, performance, or hosted CI results. The scanner's inventory operations do not read/import candidate code; interpreter startup, its own stdlib dependencies, existing `PYTHONPATH` and site hooks remain trusted. Prefer `python -I` with an absolute scanner path when reducing current-directory and `PYTHONPATH` startup exposure; this is not a sandbox guarantee.
