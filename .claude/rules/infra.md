---
paths:
  - "docker-compose.yml"
  - "Dockerfile.*"
  - "jobs/**/config.xml"
  - "init.groovy.d/**"
  - "Makefile"
  - ".gitignore"
  - ".github/workflows/*.yml"
---

# Infrastructure — boundary-crossing changes

**Use plan mode.** Everything matched by this rule needs a rebuild or a teardown
to unwind. Write the plan down before editing. (A single-function fix inside one
Python script does not need this; these files do.)

**Change one layer at a time.** Do not simultaneously edit `hunt.py`, its Jenkins
job, and the Streamlit reader — the failure becomes unattributable.

## Build and restart semantics

- `Dockerfile.jenkins` **`COPY`s the submodule at build time**. A submodule edit
  needs `make jenkins-build`, not a restart.
- Tier 0 parses these files: `docker compose config -q` and an XML parse of every
  `jobs/*/config.xml`. Run `make check` after editing either.

## Jenkins jobs

- `jobs/threatfeed-collector-job/config.xml` — cron `H 10 * * *`. Runs
  `ioc_collect.py`, **prunes `/shared` to the 30 newest files per pattern**, then
  triggers `hunt-job`. Anything you leave in `/shared` for later may be deleted
  by the 10:00 run.
- `jobs/hunt-job/config.xml` — cron `H 11 * * *`. Runs `hunt.py`, archives
  `*.csv`.

## `.gitignore` and CI are guards, not chores

`.gitignore` keeps secrets, IoC CSVs, and `report_*.md` out of git, and the
"no secrets or reports committed" step in `.github/workflows/ci.yml` fails the
build if one is ever tracked. **Do not relax either to make a commit go
through** - that is the failure mode both exist to catch.

The `*.txt` and `*.csv` entries are blanket rules, so a legitimate new file with
one of those extensions is silently skipped. Use `git check-ignore -v` when a
file you added does not show up in `git status`.

CI's Tier 0 and Tier 1 steps mirror `make check` deliberately. Change one and
change the other in the same edit, or the gate and the build drift apart.

## Security posture is deliberate

`init.groovy.d/01-security.groovy` disables Jenkins auth and the CSRF crumb
issuer; Jupyter runs with no token and `--allow-root`; MISP ships default
credentials with TLS verification off. **This is intentional and documented
under "Security Considerations" in `README.md`.** Do not "harden" it unprompted.

The only mitigating control is **network isolation**. So:

- Never bind a port beyond localhost.
- Never add a tunnel, ngrok, or any public exposure.
- Never suggest deploying this compose file anywhere shared.
- If a change would widen exposure at all, **stop and ask**.

## Lifecycle targets are human-run (Tier 2)

`make dev` needs `sudo`; `make up/down/restart/build`, the per-service targets,
and `make clean` are denied for agents in `.claude/settings.json`. Do not route
around the wall — hand the user this block:

```bash
sudo make dev            # pull + build + up --wait; extracts the MISP authkey to ./shared/authkey.txt
make status
curl -sf http://localhost/users/login >/dev/null   # MISP login page via nginx
curl -sf http://localhost:8081 >/dev/null         # Streamlit
curl -sf http://localhost:8082 >/dev/null         # Jupyter
```

`sudo make dev` sleeps 30s then reads the admin authkey out of the `db`
container. If it fails, MISP was still booting — re-run it rather than "fixing"
the Makefile.

`make dev` depends on `make pull`, which upgrades `misp-core` and `misp-nginx`:
`up --build` rebuilds only the services with a `build:` stanza, and Compose's
default pull policy for an `image:`-only service is "missing", so a cached
`misp-core:latest` would otherwise never be refreshed — not even by
`make clean`, which removes containers and volumes but no images. `make pull`
reaches ghcr.io, so it is Tier 2 as well: hand it to the user.

`make clean` destroys the MISP database and all Jenkins job history. **Confirm
with the user every time** — prior approval does not carry over.
