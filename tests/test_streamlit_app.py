"""Tests for the pure helpers in shared/streamlit.py.

Only the file-selection and text-matching helpers are covered — the rendering
code is top-level Streamlit and is deliberately not executed (see
``tests/conftest.py``). These helpers are what silently empty the dashboard when
an artifact filename contract changes, so they are the ones worth pinning.
"""


# --- filter_files_by_date -------------------------------------------------


def _touch(directory, *names):
    for name in names:
        (directory / name).write_text("x", encoding="utf-8")


def test_filter_files_by_date_selects_only_the_requested_window(dashboard, tmp_path):
    import datetime

    _touch(
        tmp_path,
        "report_2026-06-08_9_Vendor.md",
        "report_2026-06-10_13_Vendor.md",
        "report_2026-06-30_20_Vendor.md",
    )

    selected = dashboard.filter_files_by_date(
        str(tmp_path / "report_*.md"),
        datetime.date(2026, 6, 8),
        datetime.date(2026, 6, 10),
        r"report_(\d{4}-\d{2}-\d{2})",
    )

    assert sorted(p.rsplit("/", 1)[-1] for p in selected) == [
        "report_2026-06-08_9_Vendor.md",
        "report_2026-06-10_13_Vendor.md",
    ]


def test_filter_files_by_date_is_inclusive_at_both_ends(dashboard, tmp_path):
    import datetime

    _touch(tmp_path, "report_2026-06-08_1_V.md", "report_2026-06-09_2_V.md")

    selected = dashboard.filter_files_by_date(
        str(tmp_path / "report_*.md"),
        datetime.date(2026, 6, 8),
        datetime.date(2026, 6, 9),
        r"report_(\d{4}-\d{2}-\d{2})",
    )

    assert len(selected) == 2


def test_filter_files_by_date_keeps_files_with_no_parsable_date(dashboard, tmp_path):
    """Undated files are kept rather than dropped — do not 'fix' this silently."""
    import datetime

    _touch(tmp_path, "report_nodate.md")

    selected = dashboard.filter_files_by_date(
        str(tmp_path / "report_*.md"),
        datetime.date(2026, 6, 8),
        datetime.date(2026, 6, 9),
        r"report_(\d{4}-\d{2}-\d{2})",
    )

    assert len(selected) == 1


def test_filter_files_by_date_returns_empty_when_nothing_matches(dashboard, tmp_path):
    import datetime

    selected = dashboard.filter_files_by_date(
        str(tmp_path / "report_*.md"), datetime.date(2026, 6, 8), datetime.date(2026, 6, 9)
    )

    assert selected == []


# --- extract_title / extract_source ---------------------------------------


def test_extract_title_reads_the_japanese_heading(dashboard):
    content = "# Report\n\n### タイトル\nExample Campaign Analysis\n\n### 概要\n..."

    assert dashboard.extract_title(content) == "Example Campaign Analysis"


def test_extract_title_returns_none_when_absent(dashboard):
    assert dashboard.extract_title("# Report\n\nno title heading here") is None


def test_extract_source_pulls_vendor_from_filename(dashboard):
    assert dashboard.extract_source("/shared/report_2026-06-10_13_Cyble.md") == "Cyble"


def test_extract_source_handles_vendor_names_with_spaces(dashboard):
    path = "/shared/report_2026-06-08_15_The Hacker News.md"

    assert dashboard.extract_source(path) == "The Hacker News"


def test_extract_source_returns_empty_for_unexpected_names(dashboard):
    assert dashboard.extract_source("/shared/notes") == ""


# --- matches_keywords -----------------------------------------------------


def test_matches_keywords_empty_filter_matches_everything(dashboard):
    assert dashboard.matches_keywords("anything", "") is True


def test_matches_keywords_requires_every_term(dashboard):
    content = "Observed lateral movement via SMB"

    assert dashboard.matches_keywords(content, "lateral smb") is True
    assert dashboard.matches_keywords(content, "lateral kerberos") is False


def test_matches_keywords_is_case_insensitive(dashboard):
    assert dashboard.matches_keywords("Observed LATERAL movement", "lateral") is True


def test_matches_keywords_refangs_before_matching(dashboard):
    """Reports store defanged indicators; a searcher types the plain form.

    This refang is for matching only — it must never feed a request or a
    rendered link.
    """
    content = "contacted evil[.]example[.]test over HTTPS"

    assert dashboard.matches_keywords(content, "evil.example.test") is True
