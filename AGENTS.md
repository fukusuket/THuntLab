# AGENTS.md — THuntLab

## Project Overview
THuntLab is a Docker-based threat hunting laboratory. Four services collaborate around a shared volume:

| Service | Port | Role |
|---|---|---|
| Jenkins | 8080 | Runs automated hunt jobs (`shared/hunt.py`, `ioc_collect.py`) |
| Streamlit | 8081 | Visualises results from CSV files in `/shared` |
| Jupyter | 8082 | Ad-hoc analysis via `shared/note.ipynb` |
| MISP | 80/443 | Central threat intel store; all Python scripts write/read events here |

All containers mount `./shared` → `/shared`. This is the **only** cross-container data exchange mechanism — scripts write CSVs/Markdown there and Streamlit reads them.

## Developer Workflows

```bash
sudo make dev          # Build + start all services, auto-extracts MISP authkey → ./shared/authkey.txt
make logs              # Tail all container logs
make jenkins-shell     # Shell into Jenkins container for debugging
make clean             # Tear down everything including volumes
```

Run threatfeed-collector locally (outside Docker):
```bash
cd shared/threatfeed-collector
cp .env.example .env   # fill in OPENAI_API_KEY, MISP_URL, MISP_KEY, DAYS_BACK
./setup.sh             # creates venv and installs requirements.txt
source venv/bin/activate
python3 ioc_collect.py
```

## MISP Authentication
`make dev` automatically extracts the MISP admin auth key and saves it to `./shared/authkey.txt`.  
All Python scripts read it as a fallback when `MISP_KEY` env var is not set:
```python
if not MISP_KEY and Path("/shared/authkey.txt").exists():
    MISP_KEY = Path("/shared/authkey.txt").read_text().strip()
```
Default MISP credentials: `admin@admin.test` / `admin`.

## Key File Map

| File | Purpose |
|---|---|
| `shared/hunt.py` | Pulls IoCs from MISP, executes SIEM queries, writes `ibh_query_YYYYMMDD.csv` and `report_*.md` to `/shared` |
| `shared/streamlit.py` | Reads `/shared/ibh_query_*.csv`, `/shared/ioc_stats_*.csv`, `/shared/report_*.md`, `/shared/abc-*.csv` |
| `shared/threatfeed-collector/ioc_collect.py` | Fetches RSS feeds, extracts IoCs, creates MISP events, writes `ioc_stats_YYYYMMDD.csv` |
| `shared/threatfeed-collector/ioc_extract.py` | IoC extraction logic + MISP event object builder; uses `pymispwarninglists` for noise filtering |
| `shared/threatfeed-collector/thunt_advisor.py` | OpenAI GPT wrapper; translates/summarises articles using prompts in `config/prompt-*.md` |
| `shared/threatfeed-collector/config/rss_feeds.csv` | Feed list (columns: Vendor, RSS Feed URL, Blog URL, crawl_links); lines starting with `#` are comments |

## Cross-Component Data Flow
```
RSS feeds → ioc_collect.py → MISP events → hunt.py → ibh_query_*.csv / report_*.md
                           ↘ ioc_stats_*.csv
                                                    ↘ streamlit.py (dashboard)
```

## Project-Specific Conventions

- **MISP event naming**: `[VendorName] Article title` — used for deduplication via `misp.search(eventinfo=...)`.
- **IoC threshold**: A MISP event is only created when non-hash IoC count > 2 (`ioc_collect.py:339`).
- **Parallel feed processing**: `ThreadPoolExecutor` with `FEED_WORKERS` (default 8) workers in `ioc_collect.py`; `SIEM_MAX_WORKERS` controls `hunt.py` parallelism.
- **SIEM connector pattern**: `hunt.py` defines an abstract `SIEMConnector` ABC. `GenericSIEMConnector` is a stub — implement a subclass to integrate a real SIEM.
- **`.env` lookup**: Scripts search for `.env` in the script's own directory first, then the parent (`/shared`).
- **Config files**: `config/common_domains.txt` and `config/suspicious_extensions.txt` are loaded at module import time; empty files fall back to empty sets with a warning.
- **Streamlit file patterns** (all under `/shared`): `ibh_query_YYYYMMDD.csv`, `ioc_stats_YYYYMMDD.csv`, `report_YYYY-MM-DD_<id>_<vendor>.md`, `abc-process-YYYYMMDD.csv`, `abc-network-YYYYMMDD.csv`.

## Tests
```bash
cd shared/threatfeed-collector
source venv/bin/activate
python -m pytest tests/
```
Test files: `tests/test_ioc_collect.py`, `tests/test_ioc_extract.py`.

## Security Notes (Lab Only)
Jenkins has auth/CSRF disabled (`init.groovy.d/01-security.groovy`). Do **not** expose ports publicly.

