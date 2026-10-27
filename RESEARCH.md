# Research and positioning

## Primary-source facts

The following sources were inspected by the coordinating research task; implementation was performed without additional network access.

1. The Python Software Foundation's [Language Summit 2026 namespaces discussion](https://blog.python.org/2026/09/language-summit-2026-namespaces/), dated September 30, 2026, describes module-name shadowing concerns. It does **not** supply empirical incident-frequency or market-demand data. A conference discussion establishes a concrete problem class, not its prevalence.
2. [Ruff's `stdlib-module-shadowing` rule, A005](https://docs.astral.sh/ruff/rules/stdlib-module-shadowing/), already checks standard-library module shadowing. It is a credible existing alternative and the recommended first choice for general linting. This project's rationale is not that stdlib filename checks are new.
3. Python's [`sys.stdlib_module_names` documentation](https://docs.python.org/3.11/library/sys.html#sys.stdlib_module_names) defines the executing interpreter's reference, including platform-specific and disabled modules. [`sys.builtin_module_names`](https://docs.python.org/3.11/library/sys.html#sys.builtin_module_names) provides built-in names. A reference match does not establish that a module is installed or importable on the current platform.

## Inference and chosen scope

A developer reviewing multiple explicitly ordered source/generated roots may benefit from seeing concrete duplicate candidates together, while separately seeing namespace candidates and built-in exemptions. This is a plausible workflow, not validated demand. The implementation is a bounded metadata inventory: no candidate imports, no candidate content reads, no automatic environment discovery, and no actual import-resolution claim.

The no-import claim applies to inventory operations. Python interpreter startup, the scanner's own stdlib dependencies, `PYTHONPATH`, site hooks, and overlapping scanner/startup paths remain trusted. An isolated `python -I` launch with the scanner's absolute path reduces ordinary current-directory and `PYTHONPATH` exposure; it is not a sandbox or a complete startup security guarantee.

The useful distinction is the combination of explicit multiple-root ordering, local duplicate candidate lists, namespace information, and built-in exemptions. Ordinary root/path constraints and a visible Python reference make the result reviewable. No novelty, superior accuracy over established linters, Stars, adoption, or business outcome is promised.

## Fair alternatives

- **Ruff A005:** preferred for general linting in an existing project; consult its documented settings and ignore options.
- **A simple directory listing or shell script:** sufficient for a small one-off inspection, especially when structured output and explicit limits are unnecessary.
- **Python import machinery / a controlled runtime reproduction:** needed when the question is what a particular application actually imports. That has different side effects and environment dependencies; this scanner deliberately does not run it on candidate files.
- **Project-specific build checks:** useful when exact generated-root conventions and deployment layout are known; a general filename inventory cannot replace those contracts.

## Unknowns and limits

No user interviews, adoption measurements, frequency study, performance benchmark, or real application import audit was performed. Windows local tests do not establish Linux/macOS behavior. Five symlink tests were skipped locally for WinError 1314, while a real Windows junction/reparse-root test passed. Test simulation confirms the reparse attribute predicate but does not validate every Windows reparse type. Filesystem mutation races, unusual import hooks, case-insensitive resolution, and deployment-specific path setup remain outside the model.
