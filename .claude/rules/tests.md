---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
---

# `tests/` — root-repo offline tests

Tier 1 of the gate (`make check-tier1` → `pytest tests/`). Covers the pure
transforms in `shared/hunt.py` (IoC extraction, query building, the retry loop's
`-1` failure sentinel, the CSV artifact header), the file-selection and
text-matching helpers in `shared/streamlit.py`, and the agent guard hooks
(`test_hooks.py` — the allowlist, the secret guard, the `make check` gate).

A hook is a wall that fails silently: a regex slip opens it and nothing else
notices. Change one, add its case to `test_hooks.py` in the same edit.

## Two hard constraints

**Offline, always.** No MISP, no SIEM, no RSS feed, no LLM, no container. A test
that needs a network or a running service is a broken test, not a passing
feature. Use synthetic fixtures — never a real IoC, never a real report.

**Load modules by path, never via `sys.path`.** `shared/streamlit.py` shadows the
real `streamlit` package if `shared/` becomes importable. `tests/conftest.py`
holds the path-import loaders and also strips the dashboard's top-level `st.*`
calls via AST, so importing a helper does not execute the UI or read `/shared`.
Add new loaders there rather than reaching for `sys.path.insert`.

## Never reach green by weakening the check

No deleting an assertion. No `pytest.skip`. No widening an `except`. No dropping
a file from `make check`. If a check is genuinely wrong, say so and leave it red.

Same check, same failure, three times → stop and report the actual output.

## Dependencies

`requirements-dev.txt` pins the deps for these tests only; the submodule pins its
own. Do not add a dependency without saying why in the same change.
