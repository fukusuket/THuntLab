---
paths:
  - "shared/threatfeed-collector/**"
---

# `shared/threatfeed-collector` — separate repository

`github.com/fukusuket/ThreatfeedCollector`, branch `main`, pinned by commit.
**It has its own `AGENTS.md`, which is authoritative for work inside it**, and
its own CI (`.github/workflows/test.yml`, Python 3.14, `pytest -q`).

## Before you trust anything here

As of 2026-09-10 the working tree is **clean** — `git -C shared/threatfeed-collector
diff` is empty and only an untracked `__pycache__/*.pyc` shows up — and the
pointer matches `heads/main`. That has not always been true. Run
`git -C shared/threatfeed-collector status --short` and diff before assuming the
submodule's own docs match the code you are reading: if tracked files are
modified, the committed `AGENTS.md` may describe code that is not what you see.

## Test baseline: green

**`make check-submodule` → `71 passed`** (verified 2026-09-10). The known-red
baseline is gone. The local edit to `thunt_advisor.py` that used to break four
`tests/test_thunt_advisor.py` cases no longer exists — the pointer bump in
`6b07497` resolved it.

**A failure here is real.** Do not wave one through as "the known baseline", and
do not weaken the submodule's tests to reach green. This target stays out of
`make check` only because the submodule pins its own dependencies, which the
root gate does not install.

## Commit order

1. Commit **inside** the submodule first.
2. Then bump the pointer in the root repo as **its own** commit.

Do not edit files here as a side effect of root-repo work. If a change belongs
here, say so and do it deliberately. Never bump the pointer as a side effect of
unrelated work.

## Rebuild

`Dockerfile.jenkins` `COPY`s this directory at build time. Edits here need
`make jenkins-build` to reach the container — a restart is not enough.

## Do not run the pipeline

`ioc_collect.py` fetches live feeds, calls a paid LLM API per article, and writes
events into MISP. It is not a test, and it is denied in
`.claude/settings.json`. Explicit user request only.

`setup.sh` creates `venv/`, while this submodule's `AGENTS.md` documents `.venv`.
