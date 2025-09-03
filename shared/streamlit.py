import streamlit as st
import pandas as pd
import os
import glob

# Page configuration
st.set_page_config(page_title="Threat Hunting Dashboard", layout="wide")

# Page title and header
st.title("🔍 Threat Hunting Dashboard")


# CSV file loading
csv_path = "/shared/hunt.csv"

if os.path.exists(csv_path):
    # Load CSV file
    threat_data = pd.read_csv(csv_path)
    threat_data['timestamp'] = pd.to_datetime(threat_data['timestamp'])

    # Main dashboard metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_threats = len(threat_data)
        st.metric("Total Threats", total_threats)

    with col2:
        confirmed_threats = len(threat_data[threat_data['status'] == 'Confirmed'])
        st.metric("Confirmed Threats", confirmed_threats)

    with col3:
        critical_threats = len(threat_data[threat_data['severity'] == 'Critical'])
        st.metric("Critical Threats", critical_threats)

    with col4:
        investigating = len(threat_data[threat_data['status'] == 'Investigating'])
        st.metric("Under Investigation", investigating)

    # Data table
    st.subheader("📊 Threat Detection Data")

    # Filtering options
    col1, col2, col3 = st.columns(3)
    with col1:
        severity_filter = st.selectbox("Severity Filter:",
                                     ["All"] + threat_data['severity'].unique().tolist())
    with col2:
        threat_type_filter = st.selectbox("Threat Type Filter:",
                                        ["All"] + threat_data['threat_type'].unique().tolist())
    with col3:
        status_filter = st.selectbox("Status Filter:",
                                   ["All"] + threat_data['status'].unique().tolist())

    # Apply filters
    filtered_data = threat_data.copy()
    if severity_filter != "All":
        filtered_data = filtered_data[filtered_data['severity'] == severity_filter]
    if threat_type_filter != "All":
        filtered_data = filtered_data[filtered_data['threat_type'] == threat_type_filter]
    if status_filter != "All":
        filtered_data = filtered_data[filtered_data['status'] == status_filter]

    # Color coding for severity
    def highlight_severity(row):
        if row['severity'] == 'Critical':
            return ['background-color: #ffebee'] * len(row)
        elif row['severity'] == 'High':
            return ['background-color: #fff3e0'] * len(row)
        elif row['severity'] == 'Medium':
            return ['background-color: #f3e5f5'] * len(row)
        else:
            return [''] * len(row)

    st.dataframe(filtered_data.style.apply(highlight_severity, axis=1), use_container_width=True)

    # IOC analysis
    st.subheader("🔍 IOC (Indicators of Compromise) Stats")
    ioc_files = glob.glob("/shared/ioc_stats_*.csv", recursive=True)
    if ioc_files:
        all_data = []
        for file_path in ioc_files:
            try:
                df = pd.read_csv(file_path)
                all_data.append(df)
            except Exception as e:
                st.warning(f"Faied to read: {file_path} - {str(e)}")

        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df['date'] = pd.to_datetime(combined_df['date'])
            st.dataframe(combined_df, use_container_width=True)
    else:
        st.error(f"ioc_stats_*.csv file not found: {csv_path}")
        st.info("Please create /shared/ioc_stats_*.csv with cti.py")

# Footer
st.markdown("---")
st.markdown("*🛡️ Cyber Threat Hunting Dashboard - Real-time Security Monitoring*")