import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(page_title="Threat Hunting Dashboard", layout="wide")
st.title("🛡️Threat Hunting Dashboard")

end_date_default = datetime.now().date()
start_date_default = end_date_default - timedelta(days=7)
date_range = st.date_input(
    "Select date range",
    (start_date_default, end_date_default),
    key="hunt_date_range",
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = start_date_default, end_date_default

tab1, tab2 = st.tabs(["🔍 IOC Hunting", "📊 Threat Detection Data"])
all_data = []
combined_df = None
hunt_files = glob.glob("/shared/ibh_query_*.csv", recursive=True)
if hunt_files:
    for file_path in hunt_files:
        try:
            df = pd.read_csv(file_path)
            all_data.append(df)
        except Exception as e:
            st.warning(f"Failed to read: {file_path} - {str(e)}")
    combined_df = pd.concat(all_data, ignore_index=True)

with tab1:
    st.subheader(f"🔍 IOC Hunting results ")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("Found IOCs in Environment")
        if combined_df:
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
        st.markdown("Executed Search Queries")
        if combined_df:
            st.dataframe(combined_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.info("Please create /shared/ibh_query_*.csv with hunt.py")

    st.subheader(f"🔍 Collected IOCs ")
    ioc_files = glob.glob("/shared/ioc_stats_*.csv", recursive=True)
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


with tab2:
    csv_path = "/shared/hunt.csv"
    if os.path.exists(csv_path):
        st.header("Threat Detection Data")
        df = pd.read_csv(csv_path)
        # Main dashboard metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            total_threats = len(df)
            st.metric("Total Threats", total_threats)

        with col2:
            confirmed_threats = len(df[df['status'] == 'Confirmed'])
            st.metric("Confirmed Threats", confirmed_threats)

        with col3:
            critical_threats = len(df[df['severity'] == 'Critical'])
            st.metric("Critical Threats", critical_threats)

        # Filtering options
        col1, col2, col3 = st.columns(3)
        with col1:
            severity_filter = st.selectbox("Severity Filter:",
                                           ["All"] + df['severity'].unique().tolist())
        with col2:
            threat_type_filter = st.selectbox("Threat Type Filter:",
                                              ["All"] + df['threat_type'].unique().tolist())
        with col3:
            status_filter = st.selectbox("Status Filter:",
                                         ["All"] + df['status'].unique().tolist())

        # Apply filters
        filtered_data = df.copy()
        if severity_filter != "All":
            filtered_data = filtered_data[filtered_data['severity'] == severity_filter]
        if threat_type_filter != "All":
            filtered_data = filtered_data[filtered_data['threat_type'] == threat_type_filter]
        if status_filter != "All":
            filtered_data = filtered_data[filtered_data['status'] == status_filter]

        st.dataframe(filtered_data, use_container_width=True)

    else:
        st.error(f"CSV file not found: {csv_path}")
        st.info("Please ensure the hunt.csv file exists in the /shared/ directory")

# Footer
st.markdown("---")
st.markdown("*🛡️ Cyber Threat Hunting Dashboard - Real-time Security Monitoring*")