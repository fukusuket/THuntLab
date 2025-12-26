import streamlit as st
import pandas as pd
import os
import glob
import re
from datetime import datetime, timedelta


def get_filtered_hunt_files(file_pattern, start_date, end_date, date_pattern=r'(\d{4}-\d{2}-\d{2})'):
    hunt_files = glob.glob(file_pattern, recursive=True)
    filtered_hunt_files = []
    for file_path in hunt_files:
        filename = os.path.basename(file_path)
        try:
            match = re.search(date_pattern, filename)
            if match:
                date_str = match.group(1)
                file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if start_date <= file_date <= end_date:
                    filtered_hunt_files.append(file_path)
            else:
                filtered_hunt_files.append(file_path)
        except ValueError:
            filtered_hunt_files.append(file_path)

    return filtered_hunt_files


# Page configuration
st.set_page_config(page_title="Threat Hunting Dashboard", layout="wide")
st.title("🛡️Threat Hunting Dashboard")

end_date_default = datetime.now().date()
start_date_default = end_date_default - timedelta(days=2)
date_range = st.date_input(
    "Select date range",
    (start_date_default, end_date_default),
    key="hunt_date_range",
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = start_date_default, end_date_default

tab1, tab2 = st.tabs(["📄 Threat Reports", "🔍 IOC Hunting"])
all_data = []
combined_df = pd.DataFrame()
hunt_files = get_filtered_hunt_files("/shared/ibh_query_*.csv", start_date, end_date)
if hunt_files:
    for file_path in hunt_files:
        try:
            df = pd.read_csv(file_path)
            all_data.append(df)
        except Exception as e:
            st.warning(f"Failed to read: {file_path} - {str(e)}")
    combined_df = pd.concat(all_data, ignore_index=True)

with tab1:
    report_files = get_filtered_hunt_files(
        "/shared/report_*.md", start_date, end_date, r"report_(\d{4}-\d{2}-\d{2})"
    )

    report_entries = []
    for file_path in report_files:
        try:
            match = re.search(r"report_(\d{4}-\d{2}-\d{2})", os.path.basename(file_path))
            if not match:
                continue
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
            report_entries.append({"date": file_date, "path": file_path})
        except Exception as e:
            st.warning(f"Failed to parse date from {file_path}: {e}")

    # Sort reports by date (newest first) and path for stability
    report_entries = sorted(report_entries, key=lambda e: (e["date"], e["path"]), reverse=True)

    if not report_entries:
        st.info("No report_*.md files found for the selected date range.")
    else:
        for entry in report_entries:
            try:
                markdown = entry["path"]
                with open(markdown, "r", encoding="utf-8") as f:
                    content = f.read()
                title_match = re.search(r"###\s*タイトル\s*\n\s*(.+)", content)
                title_text = title_match.group(1).strip() if title_match else os.path.basename(entry["path"])
                source = ""
                match = re.search(r".*_(.*?)\.md", markdown)
                if match:
                    source = match.group(1)
                label = f"{entry['date'].strftime('%m-%d')} | {source} | {title_text}"
                lines = content.splitlines(True)
                content = "".join(lines[3:])
                with st.expander(label, expanded=False):
                    font_css = """
                    <style>
                        /* 1. 通常のMarkdownテキスト（段落、リストなど） */
                        .stMarkdown p, .stMarkdown li, .stMarkdown span{
                            font-size: 16px !important;
                        }

                        /* 2. テーブル（表）の中の文字 */
                        /* ヘッダー(th)とセル(td)の両方を指定 */
                        .stMarkdown table th, .stMarkdown table td {
                            font-size: 16px !important;
                        }

                        /* h3 見出しのサイズ設定 */
                        .stMarkdown h3 {
                            font-family: 'JetBrains Mono', monospace;
                            font-size: 18px !important;
                        }

                        /* インラインコードのサイズ設定 */
                        .stMarkdown code {
                            font-size: 16px !important;
                        }
                    </style>
                    """
                    st.markdown(font_css, unsafe_allow_html=True)
                    st.markdown(content)
            except Exception as e:
                st.warning(f"Failed to read {entry['path']}: {e}")

with tab2:
    st.subheader(f"🔍 IOC Hunting results ")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("Found IOCs in Environment")
        if not combined_df.empty:
            filtered_df = combined_df[combined_df['Count'] > 0]
            if filtered_df.empty:
                st.info("No IoCs were detected during the specified search period.")
            else:
                st.error('IoCs were detected during the specified search period.', icon="🚨")
                cols = [c for c in ['Value', 'Count'] if c in filtered_df.columns]
                filtered_df = filtered_df.loc[:, cols]
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        else:
            st.info("Please create /shared/ibh_hunt_*.csv with hunt.py")

    with col2:
        st.markdown(f"Executed Search Queries")
        if not combined_df.empty:
            st.info(f"{len(combined_df)} queries were executed.")
            st.dataframe(combined_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.info("Please create /shared/ibh_query_*.csv with hunt.py")

    st.subheader(f"🔍 Collected IOCs ")
    ioc_files = get_filtered_hunt_files("/shared/ioc_stats_*.csv", start_date, end_date)
    if ioc_files:
        all_data = []
        for file_path in ioc_files:
            try:
                df = pd.read_csv(file_path)
                all_data.append(df)
            except Exception as e:
                st.warning(f"Failed to read: {file_path} - {str(e)}")

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df['date'] = pd.to_datetime(combined_df['date'])
            combined_df['date'] = pd.to_datetime(combined_df['date']).dt.date
            combined_df = combined_df.sort_values('date', ascending=False)
            combined_df = combined_df[
                (combined_df['date'] >= start_date) &
                (combined_df['date'] <= end_date)
                ]
            st.dataframe(combined_df, use_container_width=True, hide_index=True)
    else:
        st.info("Please create /shared/ioc_stats_*.csv with cti.py")


# Footer
st.markdown("---")
st.markdown("*🛡️ Cyber Threat Hunting Dashboard - Real-time Security Monitoring*")