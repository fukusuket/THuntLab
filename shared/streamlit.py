import streamlit as st
import pandas as pd
import os
import glob
import re
from datetime import datetime, timedelta
from typing import List, Optional


def filter_files_by_date(pattern: str, start_date, end_date, date_regex: str = r'(\d{4}-\d{2}-\d{2})') -> List[str]:
    files = glob.glob(pattern, recursive=True)
    filtered = []
    for path in files:
        try:
            match = re.search(date_regex, os.path.basename(path))
            if match:
                file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()
                if start_date <= file_date <= end_date:
                    filtered.append(path)
            else:
                filtered.append(path)
        except ValueError:
            filtered.append(path)
    return filtered


def load_csvs(paths: List[str]) -> pd.DataFrame:
    dfs = []
    for path in paths:
        try:
            dfs.append(pd.read_csv(path))
        except Exception as e:
            st.warning(f"Failed to read: {path} - {str(e)}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def extract_title(content: str) -> Optional[str]:
    match = re.search(r"###\s*タイトル\s*\n\s*(.+)", content)
    return match.group(1).strip() if match else None


def extract_source(path: str) -> str:
    match = re.search(r".*_(.*?)\.md", path)
    return match.group(1) if match else ""


def matches_keywords(content: str, keywords: str) -> bool:
    if not keywords:
        return True
    content = content.replace("[.]", ".")
    return all(k in content.lower() for k in keywords.lower().split())


font_css = """
<style>
    .stMarkdown p, .stMarkdown li, .stMarkdown span{
        font-size: 14px !important;
    }
    .stMarkdown table th, .stMarkdown table td {
        font-size: 14px !important;
    }
    .stMarkdown h3 {
        font-size: 18px !important;
    }
    .stMarkdown code {
        font-size: 14px !important;
    }
</style>
"""

st.markdown(font_css, unsafe_allow_html=True)
st.set_page_config(page_title="Threat Hunting Dashboard", layout="wide")
st.title("🛡️Threat Hunting Dashboard")

end_date = datetime.now().date()
start_date = end_date - timedelta(days=2)
date_range = st.date_input("", (start_date, end_date), key="hunt_date_range")

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range

hunt_files = filter_files_by_date("/shared/ibh_query_*.csv", start_date, end_date)
if hunt_files:
    latest = max(hunt_files, key=lambda p: datetime.strptime(re.search(r'(\d{8})', os.path.basename(p)).group(1), "%Y%m%d"))
    hunt_files = [latest]
hunt_df = load_csvs(hunt_files)
if not hunt_df.empty:
    hunt_df['To'] = pd.to_datetime(hunt_df['To']).dt.date
    hunt_df = hunt_df[(hunt_df['To'] >= start_date) & (hunt_df['To'] <= end_date)]
    hunt_df = hunt_df.drop_duplicates().sort_values(by="Count", ascending=False)

tab1, tab2 = st.tabs(["📊 Threat Reports", "🕵️ IOC Hunting"])

with tab1:
    report_files = filter_files_by_date("/shared/report_*.md", start_date, end_date, r"report_(\d{4}-\d{2}-\d{2})")
    reports = []
    for path in report_files:
        try:
            match = re.search(r"report_(\d{4}-\d{2}-\d{2})", os.path.basename(path))
            if match:
                reports.append({"date": datetime.strptime(match.group(1), "%Y-%m-%d").date(), "path": path})
        except Exception as e:
            st.warning(f"Failed to parse date from {path}: {e}")

    if not reports:
        st.info("No report_*.md files found for the selected date range.")
    else:
        col1, col2 = st.columns([1, 1])
        with col1:
            keyword = st.text_input("🔍 Keyword Filter", placeholder="Enter keywords separated by spaces (e.g., ransomware phishing)")
        with col2:
            sort_order = st.radio("↕️ Sort", ["New → Old", "Old → New"], horizontal=True)

        reports = sorted(reports, key=lambda e: (e["date"], e["path"]), reverse=(sort_order == "New → Old"))
        for entry in reports:
            try:
                with open(entry["path"], "r", encoding="utf-8") as f:
                    content = f.read()
                if not content.strip():
                    continue
                if not matches_keywords(f"{content}\n{entry['path']}", keyword):
                    continue

                title = extract_title(content) or os.path.basename(entry["path"])
                source = extract_source(entry["path"])
                label = f"{entry['date'].strftime('%m-%d')} | {source} | {title}"

                lines = content.splitlines(True)
                formatted = "".join(lines[3:]).replace("### 概要", f"### {title}")

                with st.expander(label, expanded=False):
                    st.markdown(formatted)
            except Exception as e:
                st.warning(f"Failed to read {entry['path']}: {e}")

with tab2:
    st.subheader("IOC Hunting results")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("Found IOCs in Environment")
        if not hunt_df.empty:
            detected = hunt_df[hunt_df['Count'] > 0]
            if detected.empty:
                st.info("No IoCs were detected during the specified search period.")
            else:
                st.error('IoCs were detected during the specified search period.', icon="🚨")
                cols = [c for c in ['Value', 'Count'] if c in detected.columns]
                st.dataframe(detected.loc[:, cols], use_container_width=True, hide_index=True, height=200)
        else:
            st.info("Please create /shared/ibh_hunt_*.csv with hunt.py")

    with col2:
        st.markdown("Executed Search Queries")
        if not hunt_df.empty:
            st.info(f"{len(hunt_df)} queries were executed.")
            st.dataframe(hunt_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.info("Please create /shared/ibh_query_*.csv with hunt.py")

    st.subheader("Collected IOCs")
    ioc_files = filter_files_by_date("/shared/ioc_stats_*.csv", start_date, end_date)
    if ioc_files:
        ioc_df = load_csvs(ioc_files)
        if not ioc_df.empty:
            ioc_df['date'] = pd.to_datetime(ioc_df['date']).dt.date
            ioc_df = ioc_df.sort_values('date', ascending=False)
            ioc_df = ioc_df[(ioc_df['date'] >= start_date) & (ioc_df['date'] <= end_date)]
            ioc_df = ioc_df.drop_duplicates()
            st.dataframe(ioc_df, use_container_width=True, hide_index=True)
    else:
        st.info("Please create /shared/ioc_stats_*.csv with cti.py")

st.markdown("---")
st.markdown("*🛡️ Cyber Threat Hunting Dashboard - Real-time Security Monitoring*")