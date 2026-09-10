---
paths:
  - "shared/hunt.py"
  - "shared/streamlit.py"
  - "shared/note.ipynb"
---

# `shared/` Python scripts

These two scripts are covered by `tests/`. **New behaviour gets a test in the
same change**, or you say explicitly which behaviour is unverified and why.

## Artifact filename contracts — these are an API

`shared/streamlit.py` globs `/shared` for fixed patterns. Renaming an output file
does not break a build; it **silently empties the dashboard**.

| Pattern | Produced by | Consumed at |
|---|---|---|
| `ibh_query_YYYYMMDD.csv` | `hunt.py` | `streamlit.py:82` |
| `ioc_stats_YYYYMMDD.csv` | `ioc_collect.py` | `streamlit.py:162` |
| `report_YYYY-MM-DD_<eventid>_<vendor>.md` | `hunt.py` (`EventReport[1]`, JP) | `streamlit.py:95` |
| `abc-process-YYYYMMDD.csv` | external | `streamlit.py:205` |
| `abc-network-YYYYMMDD.csv` | external | `streamlit.py:206` |

Rename one only together with every glob in `streamlit.py` and every test that
pins it. `report_*` is additionally parsed by the regex at `streamlit.py:99`.

## MISP event naming

`[VendorName] Article title`. This string is both the dedup key
(`misp.search(eventinfo=...)`) and the source `hunt.py` regexes `\[([^\]]+)\]`
out of for report filenames. Changing the format breaks both.

## Config resolution

- `hunt.py` loads **only** `Path(__file__).with_name(".env")` (line 33). The
  submodule's scripts differ: own directory first, then parent.
- **MISP key fallback**: when `MISP_KEY` is unset, scripts read
  `/shared/authkey.txt`. Preserve this in any script you add — it is what makes
  containerised runs work with no configuration.
- Config text files load at module import; an empty file degrades to an empty set
  with a warning rather than failing.

## Conventions

- **Defanged-only extraction**: URLs and IPs are extracted only in defanged form
  (`[.]`, `hxxp`, `[://]`). Hashes and Chrome extension IDs (`[a-p]{32}`) are
  scanned from full text.
- **IoC threshold**: an event is created only when non-hash IoC count > 2
  (`ioc_collect.py:339`).
- **Parallelism**: `SIEM_MAX_WORKERS` (default 4) in `hunt.py`;
  `FEED_WORKERS` (default 8) in `ioc_collect.py`. Both `ThreadPoolExecutor`.
- **SIEM connectors**: `hunt.py` defines the `SIEMConnector` ABC.
  `GenericSIEMConnector` is a deliberate stub returning 0. Integrate a real SIEM
  by **subclassing**, not by editing the stub.
- **Python 3.14** in containers and CI. Do not add syntax the local interpreter
  parses but the images cannot.

## Known bugs — verified, fix only when asked

- **`hunt.py` `MISP_KEY` guard is inverted** (lines 226-231):
  `if not misp_key and Path("/shared/authkey.txt").exists(): ... else: error; exit(1)`.
  When `MISP_KEY` *is* set in the environment it takes the `else` branch and
  exits 1. Only the authkey-file path works today.
- `shared/.env.example` declares `SIEM_PASSWORD`, but `hunt.py` reads
  `os.getenv('SIEM_PASS', ...)` (line 239). It also declares no `MISP_KEY`.

## Running them

`hunt.py` reaches MISP and the SIEM — it is not offline verification, and it is
gated behind an `ask` rule. Verify with `make check`, not by running the script.
