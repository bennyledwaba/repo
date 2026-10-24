import streamlit as st
import pandas as pd
import hashlib
import io
import numpy as np
import plotly.express as px
from datetime import datetime

# -----------------------
# Helper functions
# -----------------------
def hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of the given password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_session_state():
    """Initialize session state keys and mock databases."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "role" not in st.session_state:
        st.session_state.role = ""
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    if "uploaded_dfs" not in st.session_state:
        st.session_state.uploaded_dfs = {}
    if "processed_file_ids" not in st.session_state:
        st.session_state.processed_file_ids = set()

    user_columns = ["username", "password", "role", "status", "created_at"]
    worker_columns = ["worker_id", "full_name", "department", "role", "induction_status", "medical_clearance"]
    incident_columns = ["incident_id", "date_logged", "classification", "risk_rating", "logged_by", "status"]
    equipment_columns = ["asset_id", "category", "assigned_location", "status", "hours_run"]

    if "users_db" not in st.session_state:
        st.session_state["users_db"] = pd.DataFrame([
            {"username": "admin", "password": hash_password("admin123"), "role": "Administrator", "status": "Active", "created_at": "2026-08-18 12:00:00"},
            {"username": "safety1", "password": hash_password("safety123"), "role": "Safety Officer", "status": "Active", "created_at": "2026-08-18 12:05:00"},
            {"username": "eng1", "password": hash_password("eng123"), "role": "Mining Engineer", "status": "Active", "created_at": "2026-08-18 12:10:00"}
        ], columns=user_columns)

    if "workers_db" not in st.session_state:
        st.session_state["workers_db"] = pd.DataFrame([
            {"worker_id": "KWM-001", "full_name": "Thabo Dlamini", "department": "Production", "role": "Drill Operator", "induction_status": "Passed", "medical_clearance": "Fit"},
            {"worker_id": "KWM-002", "full_name": "Aphiwe Nkosi", "department": "Maintenance", "role": "Technician", "induction_status": "Passed", "medical_clearance": "Fit"},
            {"worker_id": "KWM-003", "full_name": "Lerato Moloi", "department": "Safety", "role": "Safety Auditor", "induction_status": "Passed", "medical_clearance": "Fit"}
        ], columns=worker_columns)

    if "incidents_db" not in st.session_state:
        st.session_state["incidents_db"] = pd.DataFrame([
            {"incident_id": "INC-001", "date_logged": "2026-08-15 08:30:00", "classification": "Equipment Scrape", "risk_rating": "Medium", "logged_by": "safety1", "status": "Resolved"},
            {"incident_id": "INC-002", "date_logged": "2026-08-17 10:45:00", "classification": "Unsafe Behaviour", "risk_rating": "High", "logged_by": "safety1", "status": "Investigating"},
            {"incident_id": "INC-003", "date_logged": "2026-08-19 14:20:00", "classification": "Ventilation Concern", "risk_rating": "Critical", "logged_by": "safety1", "status": "Open"}
        ], columns=incident_columns)

    if "equipment_db" not in st.session_state:
        st.session_state["equipment_db"] = pd.DataFrame([
            {"asset_id": "EQP-01", "category": "LHD Loader", "assigned_location": "Level 3 - North Block", "status": "Operational", "hours_run": "1420"},
            {"asset_id": "EQP-02", "category": "Truck", "assigned_location": "Level 2 - East Pit", "status": "Under Maintenance", "hours_run": "2890"},
            {"asset_id": "EQP-03", "category": "Drill Rig", "assigned_location": "Level 1 - South Shaft", "status": "Operational", "hours_run": "1760"}
        ], columns=equipment_columns)

@st.cache_data
def read_csv_bytes(file_bytes: bytes, **kwargs) -> pd.DataFrame:
    """Read CSV/Excel bytes into a pandas DataFrame."""
    return pd.read_csv(io.BytesIO(file_bytes), **kwargs)

def read_excel_bytes(file_bytes: bytes, **kwargs) -> pd.DataFrame:
    """Read Excel bytes into a pandas DataFrame."""
    return pd.read_excel(io.BytesIO(file_bytes), **kwargs)

def add_uploaded_file(uploaded_file):
    """Add uploaded file to session_state.uploaded_dfs with unique name."""
    try:
        name = uploaded_file.name
        file_bytes = uploaded_file.read()

        if name.lower().endswith((".xlsx", ".xls")):
            df = read_excel_bytes(file_bytes)
        else:
            df = read_csv_bytes(file_bytes)

        base = name.rsplit(".", 1)[0] if "." in name else name
        ext = name.rsplit(".", 1)[1] if "." in name else "csv"
        final_name = name
        i = 1
        while final_name in st.session_state.uploaded_dfs:
            final_name = f"{base} ({i}).{ext}"
            i += 1

        st.session_state.uploaded_dfs[final_name] = df
        st.success(f"Uploaded: {final_name} — shape: {df.shape}")
    except Exception as e:
        st.error(f"Failed to read {uploaded_file.name}: {e}")

def filter_dataframe(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply numeric and categorical filters to a dataframe."""
    out = df.copy()
    for col, cfg in filters.items():
        if cfg["type"] == "numeric":
            lo, hi = cfg["value"]
            out = out[(out[col] >= lo) & (out[col] <= hi)]
        else:
            vals = cfg["value"]
            if vals:
                out = out[out[col].isin(vals)]
    return out

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

# -----------------------
# App UI
# -----------------------
st.set_page_config(page_title="Khwezi Mining App", page_icon="⛏️", layout="wide")
init_session_state()

st.title("⛏️ Khwezi Mining Health, Safety & Equipment System")
st.write("Wits MINN2020A Project - Access Control & Security Prototype")

if not st.session_state.logged_in:
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        users_db = st.session_state["users_db"]
        match = users_db[users_db["username"] == username]
        if match.empty:
            st.error("Invalid username or password.")
        else:
            stored_hash = match.iloc[0]["password"]
            if hash_password(password) == stored_hash:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = match.iloc[0]["role"]
                st.session_state.login_attempts = 0
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                st.error(f"Invalid username or password. Attempts: {st.session_state.login_attempts}")
    st.stop()

current_username = st.session_state["username"]
current_role = st.session_state["role"]

st.sidebar.header("🛡️ Current User Session")
st.sidebar.write(f"Logged in as: **{current_username}**")
st.sidebar.write(f"Role: **{current_role}**")

if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.session_state["login_attempts"] = 0
    st.session_state["uploaded_dfs"] = {}
    st.session_state["processed_file_ids"].clear()
    st.rerun()

allowed_tabs = ["View Dashboard"]
if current_role == "Administrator":
    allowed_tabs = ["View Dashboard", "Worker Safety Data", "Safety Incidents", "Risk Assessment", "Equipment Data", "Maintenance Data", "Generate Reports", "Manage Users Console"]
elif current_role == "Safety Officer":
    allowed_tabs = ["View Dashboard", "Worker Safety Data", "Safety Incidents", "Risk Assessment", "Generate Reports"]
elif current_role == "Mining Engineer":
    allowed_tabs = ["View Dashboard", "Worker Safety Data", "Safety Incidents", "Risk Assessment", "Equipment Data", "Maintenance Data", "Generate Reports"]

st.sidebar.subheader("Navigation Menu")
chosen_tab = st.sidebar.radio("Authorized Modules:", allowed_tabs)

if chosen_tab == "View Dashboard":
    st.header("📈 Main Monitoring Dashboard")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Users Managed", len(st.session_state["users_db"]))
    with col2:
        st.metric("Workers Registered", len(st.session_state["workers_db"]))
    with col3:
        st.metric("Logged Safety Incidents", len(st.session_state["incidents_db"]))

    st.markdown("---")
    st.subheader("📊 Operational Analytics & CSV Workspace")

    st.sidebar.markdown("---")
    st.sidebar.header("CSV Upload & Files")
    uploaded = st.sidebar.file_uploader(
        ":file_folder: Upload CSV or Excel files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )

    if uploaded:
        for f in uploaded:
            file_id = f"{f.name}_{f.size}"
            if file_id not in st.session_state.processed_file_ids:
                add_uploaded_file(f)
                st.session_state.processed_file_ids.add(file_id)

    if not st.session_state.uploaded_dfs:
        st.sidebar.info("No CSV uploaded. You can upload one or click below to load a sample dataset.")
        if st.sidebar.button("Load sample dataset"):
            sample = pd.DataFrame({
                "sepal_length": np.random.normal(5.8, 0.8, 150),
                "sepal_width": np.random.normal(3.0, 0.4, 150),
                "petal_length": np.random.normal(3.7, 1.5, 150),
                "petal_width": np.random.normal(1.2, 0.8, 150),
                "species": np.random.choice(["setosa", "versicolor", "virginica"], 150)
            })
            st.session_state.uploaded_dfs["sample_iris.csv"] = sample
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("Dashboard Settings")
    show_table = st.sidebar.checkbox("Show table", value=True)
    show_summary = st.sidebar.checkbox("Show summary (describe)", value=True)
    show_charts = st.sidebar.checkbox("Show charts", value=True)

    if st.session_state.uploaded_dfs:
        file_list = list(st.session_state.uploaded_dfs.keys())
        selected_file = st.sidebar.selectbox("Select CSV file", options=file_list)
        df = st.session_state.uploaded_dfs[selected_file]

        st.markdown(f"#### Processing File: `{selected_file}`")
        st.write(f"**Rows:** {df.shape[0]} — **Columns:** {df.shape[1]}")

        with st.expander("Column info and nulls"):
            info_df = pd.DataFrame({
                "dtype": df.dtypes.astype(str),
                "n_missing": df.isna().sum(),
                "n_unique": df.nunique(dropna=False)
            })
            st.dataframe(info_df, use_container_width=True)

        st.sidebar.header("Data Target Filters")
        filters = {}
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=np.number).columns.tolist()

        for col in numeric_cols:
            min_val = float(df[col].min())
            max_val = float(df[col].max())
            filters[col] = {
                "type": "numeric",
                "value": (min_val, max_val)
            }

        if categorical_cols:
            for col in categorical_cols:
                vals = sorted(df[col].dropna().unique().tolist())
                default_vals = vals[: min(5, len(vals))]
                filters[col] = {
                    "type": "categorical",
                    "value": st.sidebar.multiselect(f"{col}", options=vals, default=default_vals)
                }

        filtered_df = filter_dataframe(df, filters)

        if show_table:
            st.subheader("Filtered Data Table")
            st.dataframe(filtered_df, use_container_width=True)

        if show_summary:
            st.subheader("Summary Statistics")
            st.write(filtered_df.describe(include="all").transpose())

        if show_charts and not filtered_df.empty:
            st.subheader("Visualization")
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                if filtered_df.shape[1] >= 2:
                    numeric_cols_vis = filtered_df.select_dtypes(include=np.number).columns.tolist()
                    if len(numeric_cols_vis) >= 2:
                        x_col = st.selectbox("X axis", numeric_cols_vis, index=0)
                        y_col = st.selectbox("Y axis", numeric_cols_vis, index=1 if 1 < len(numeric_cols_vis) else 0)
                        fig = px.scatter(filtered_df, x=x_col, y=y_col, color=filtered_df.columns[0] if filtered_df.columns[0] in filtered_df.select_dtypes(exclude=np.number).columns else None)
                        st.plotly_chart(fig, use_container_width=True)

            with chart_col2:
                if filtered_df.select_dtypes(include=np.number).columns.size > 0:
                    hist_col = st.selectbox("Histogram column", filtered_df.select_dtypes(include=np.number).columns.tolist(), index=0)
                    hist_fig = px.histogram(filtered_df, x=hist_col)
                    st.plotly_chart(hist_fig, use_container_width=True)

elif chosen_tab == "Worker Safety Data":
    st.header("👷 Worker Safety Data")
    workers_df = st.session_state["workers_db"]
    st.dataframe(workers_df, use_container_width=True)

    if not workers_df.empty:
        dept_counts = workers_df["department"].value_counts()
        st.subheader("Department Breakdown")
        st.bar_chart(dept_counts)

elif chosen_tab == "Safety Incidents":
    st.header("🚨 Safety Incidents")
    incidents_df = st.session_state["incidents_db"]
    st.dataframe(incidents_df, use_container_width=True)

    if not incidents_df.empty:
        status_counts = incidents_df["status"].value_counts()
        st.subheader("Incident Status Overview")
        st.bar_chart(status_counts)

elif chosen_tab == "Risk Assessment":
    st.header("⚠️ Risk Assessment")
    incidents_df = st.session_state["incidents_db"]

    if incidents_df.empty:
        st.info("No incident data available.")
    else:
        risk_order = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        mapped = incidents_df.copy()
        mapped["risk_score"] = mapped["risk_rating"].map(risk_order).fillna(0)

        st.dataframe(mapped[["incident_id", "classification", "risk_rating", "status"]], use_container_width=True)

        fig = px.bar(
            mapped,
            x="incident_id",
            y="risk_score",
            color="risk_rating",
            title="Risk score by incident"
        )
        st.plotly_chart(fig, use_container_width=True)

elif chosen_tab == "Equipment Data":
    st.header("🛠️ Equipment Data")
    equipment_df = st.session_state["equipment_db"]
    st.dataframe(equipment_df, use_container_width=True)

    if not equipment_df.empty:
        equipment_df["hours_run"] = pd.to_numeric(equipment_df["hours_run"], errors="coerce")
        fig = px.bar(
            equipment_df,
            x="asset_id",
            y="hours_run",
            color="status",
            title="Hours Run by Asset"
        )
        st.plotly_chart(fig, use_container_width=True)

elif chosen_tab == "Maintenance Data":
    st.header("🔧 Maintenance Data")
    maintenance_df = pd.DataFrame({
        "asset_id": ["EQP-01", "EQP-02", "EQP-03"],
        "last_service": ["2026-07-09", "2026-08-01", "2026-08-20"],
        "next_service_due": ["2026-10-09", "2026-11-01", "2026-10-20"],
        "status": ["Healthy", "Due", "Operational"]
    })
    st.dataframe(maintenance_df, use_container_width=True)

    fig = px.timeline(
        maintenance_df,
        x_start="last_service",
        x_end="next_service_due",
        y="asset_id",
        color="status"
    )
    st.plotly_chart(fig, use_container_width=True)

elif chosen_tab == "Generate Reports":
    st.header("📄 Generate Reports")
    st.write("Generate summary reports from company data.")

    report_type = st.selectbox("Select report type", ["Worker Summary", "Incident Summary", "Equipment Summary"])
    if report_type == "Worker Summary":
        report_df = st.session_state["workers_db"]
    elif report_type == "Incident Summary":
        report_df = st.session_state["incidents_db"]
    else:
        report_df = st.session_state["equipment_db"]

    st.dataframe(report_df, use_container_width=True)

    csv_bytes = df_to_csv_bytes(report_df)
    st.download_button(
        label=f"Download {report_type} CSV",
        data=csv_bytes,
        file_name=f"{report_type.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

elif chosen_tab == "Manage Users Console":
    st.header("🧑‍💼 Manage Users Console")
    users_df = st.session_state["users_db"]

    st.subheader("Current User Registry")
    st.dataframe(users_df, use_container_width=True)

    with st.form("add_user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["Administrator", "Safety Officer", "Mining Engineer"])
        submitted = st.form_submit_button("Add User")

    if submitted and new_username.strip():
        if new_username in users_df["username"].values:
            st.warning("Username already exists.")
        else:
            new_row = {
                "username": new_username,
                "password": hash_password(new_password),
                "role": new_role,
                "status": "Active",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state["users_db"] = pd.concat(
                [users_df, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"User '{new_username}' added successfully.")
            st.rerun()
