"""Tests for shared/hunt.py.

Covers the pure transforms and the retry loop. No MISP, no SIEM, no network:
``GenericSIEMConnector`` is never used against a real host and every connector
here is a local fake.
"""

import csv
from datetime import datetime, timedelta


# --- extract_iocs ---------------------------------------------------------


def _event(event_id, attributes):
    return {"Event": {"id": event_id, "Attribute": attributes}}


def test_extract_iocs_keeps_only_requested_types(hunt):
    events = [
        _event(
            "11",
            [
                {"type": "ip-dst", "value": "203.0.113.10"},
                {"type": "sha256", "value": "a" * 64},
                {"type": "comment", "value": "ignore me"},
            ],
        )
    ]

    iocs = hunt.extract_iocs(events, ["ip-dst", "sha256"])

    assert [(i.type, i.value, i.event_id) for i in iocs] == [
        ("ip-dst", "203.0.113.10", "11"),
        ("sha256", "a" * 64, "11"),
    ]


def test_extract_iocs_flattens_across_events(hunt):
    events = [
        _event("1", [{"type": "hostname", "value": "a.example.test"}]),
        _event("2", [{"type": "hostname", "value": "b.example.test"}]),
    ]

    assert len(hunt.extract_iocs(events, ["hostname"])) == 2


def test_extract_iocs_tolerates_malformed_events(hunt):
    """MISP responses are not guaranteed to carry Event or Attribute keys."""
    events = [{}, {"Event": {"id": "3"}}, _event("4", [])]

    assert hunt.extract_iocs(events, ["ip-dst"]) == []


# --- build_search_query ---------------------------------------------------


def test_build_search_query_per_type(hunt):
    IoC = hunt.IoC
    assert hunt.build_search_query(IoC("ip-dst", "203.0.113.10", "1")) == 'dest_ip="203.0.113.10"'
    assert hunt.build_search_query(IoC("sha256", "abc", "1")) == 'file_hash="abc"'
    hostname = hunt.build_search_query(IoC("hostname", "evil.example.test", "1"))
    assert 'hostname="evil.example.test"' in hostname
    assert 'dns_query="evil.example.test"' in hostname


def test_build_search_query_falls_back_for_unknown_type(hunt):
    query = hunt.build_search_query(hunt.IoC("url", "hxxp://evil[.]test", "1"))
    assert query == 'value="hxxp://evil[.]test"'


# --- create_search_queries ------------------------------------------------


def test_create_search_queries_spans_requested_window(hunt):
    iocs = [hunt.IoC("ip-dst", "203.0.113.10", "1")]

    queries = hunt.create_search_queries(iocs, search_days=90)

    assert len(queries) == 1
    span = queries[0].to_date - queries[0].from_date
    assert span == timedelta(days=90)
    assert queries[0].count == 0


# --- execute_single_search (retry loop) -----------------------------------


class _FlakyConnector:
    """Fails ``failures`` times, then returns ``result``."""

    def __init__(self, failures, result=7):
        self.failures = failures
        self.result = result
        self.calls = 0

    def login(self, host, username, password):
        return True

    def execute_search(self, query, from_date, to_date):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("SIEM unavailable")
        return self.result


def _query(hunt):
    now = datetime.now()
    return hunt.SearchQuery(
        from_date=now - timedelta(days=1), to_date=now, value="v", query="q", count=0
    )


def test_execute_single_search_succeeds_first_try(hunt):
    siem = _FlakyConnector(failures=0)

    result = hunt.execute_single_search(siem, _query(hunt), retry_count=3, retry_interval=0)

    assert result.count == 7
    assert siem.calls == 1


def test_execute_single_search_retries_then_succeeds(hunt, monkeypatch):
    monkeypatch.setattr(hunt.time, "sleep", lambda _: None)
    siem = _FlakyConnector(failures=2)

    result = hunt.execute_single_search(siem, _query(hunt), retry_count=3, retry_interval=5)

    assert result.count == 7
    assert siem.calls == 3


def test_execute_single_search_marks_exhausted_retries_as_minus_one(hunt, monkeypatch):
    """-1 is the sentinel that distinguishes 'search failed' from '0 hits'."""
    monkeypatch.setattr(hunt.time, "sleep", lambda _: None)
    siem = _FlakyConnector(failures=99)

    result = hunt.execute_single_search(siem, _query(hunt), retry_count=3, retry_interval=5)

    assert result.count == -1
    assert siem.calls == 3


def test_execute_siem_searches_returns_one_result_per_query(hunt):
    queries = [_query(hunt) for _ in range(5)]

    results = hunt.execute_siem_searches(_FlakyConnector(failures=0), queries, max_workers=2)

    assert len(results) == 5
    assert all(r.count == 7 for r in results)


# --- save_query_history ---------------------------------------------------


def test_save_query_history_writes_expected_header_and_rows(hunt, tmp_path):
    """Streamlit reads this CSV; the header is part of the artifact contract."""
    out = tmp_path / "ibh_query_20260829.csv"
    now = datetime(2026, 8, 29)
    queries = [
        hunt.SearchQuery(
            from_date=now - timedelta(days=90),
            to_date=now,
            value="203.0.113.10",
            query='dest_ip="203.0.113.10"',
            count=3,
        )
    ]

    hunt.save_query_history(queries, str(out))

    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0] == ["From", "To", "Count", "Value", "Query"]
    assert rows[1] == ["2026-05-31", "2026-08-29", "3", "203.0.113.10", 'dest_ip="203.0.113.10"']
