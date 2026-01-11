import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import json

# =================================================================
# --- 0. FIREBASE SETUP ---
# =================================================================

SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json' 
EMPLOYEE_COLLECTION = "employees" 

@st.cache_resource
def initialize_firebase():
    try:
        if not firebase_admin._apps:
            if st.secrets.get("firebase_config"):
                final_credentials = dict(st.secrets["firebase_config"])
                if isinstance(final_credentials.get('private_key'), str):
                     final_credentials['private_key'] = final_credentials['private_key'].replace('\\n', '\n')
                cred = credentials.Certificate(final_credentials)
            else:
                with open(SERVICE_ACCOUNT_FILE) as f:
                    service_account_info = json.load(f)
                cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        st.error(f"❌ Firebase Error: {e}")
        return None

db = initialize_firebase()

# =================================================================
# --- 1. DATA FUNCTIONS ---
# =================================================================

def get_all_employees():
    data = []
    if db is None: return pd.DataFrame()
    try:
        docs = db.collection(EMPLOYEE_COLLECTION).stream()
        for doc in docs:
            record = doc.to_dict()
            record['id'] = doc.id 
            data.append(record)
        df = pd.DataFrame(data) if data else pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}"); return pd.DataFrame()

def clean_data(data):
    # Empty strings ko None banana taaki Firestore clean rahe
    return {k: (v.strip() if isinstance(v, str) and v.strip() != "" else v) for k, v in data.items() if k}

# =================================================================
# --- 2. AUTHENTICATION (FIXED LOGIC) ---
# =================================================================

st.set_page_config(layout="wide", page_title="Railway Management System")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def check_login():
    if st.session_state['authenticated']:
        return True
    
    st.title("🔒 Login")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Enter System")
        if submit:
            if u == st.secrets["app_auth"]["username"] and p == st.secrets["app_auth"]["password"]:
                st.session_state['authenticated'] = True
                st.rerun() # Refresh to show main app
            else:
                st.error("Invalid Username or Password")
    return False

if not check_login():
    st.stop()

# =================================================================
# --- 3. MAIN APP CODE ---
# =================================================================

employee_df = get_all_employees()
DOC_ID_KEY = 'id'
EMPLOYEE_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें (Add New)"

# Aapki list ke anusar saare 38 columns
ALL_COLS = [
    'S. No.', 'PF Number', 'HRMS ID', 'Seniority No.', 'Unit', 'Employee Name', "FATHER'S NAME", 
    'Designation', 'STATION', 'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'Employee Name in Hindi', 
    'SF-11 short name', 'Gender ', 'Category', 'Designation in Hindi', 'Posting status', 
    'APPOINTMENT TYPE', 'PRMOTION DATE', 'DOR', 'Medical category', 'LAST PME', 'PME DUE', 
    'MEDICAL PLACE', 'LAST TRAINING', 'TRAINING DUE', 'SERVICE REMARK', 'EMPTYPE', 
    'PRAN', 'PENSIONACCNO', 'RAIL QUARTER NO.', 'CUG NUMBER', 'E-Number', 'UNIT No.', 
    'SICK FROM Date', 'PF No.'
]

def get_unique_opts(col_name):
    if not employee_df.empty and col_name in employee_df.columns:
        return sorted([str(x) for x in employee_df[col_name].dropna().unique() if str(x).strip() != ""])
    return []

# Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📊 Dashboard/Summary", "➕ Add Employee", "✏️ Edit/Update All Columns"])

# --- TAB 1: SUMMARY ---
with tab1:
    st.header("📋 Current Status")
    if not employee_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Employees", len(employee_df))
        
        # PME Due check
        if 'PME DUE' in employee_df.columns:
            st.subheader("⚠️ PME Alerts")
            pme_df = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")]
            st.dataframe(pme_df[['Employee Name', 'Designation', 'PME DUE']], hide_index=True)
        
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("No records found.")

# --- TAB 2: ADD (EDITABLE DROPDOWNS) ---
with tab2:
    st.header("➕ Add New Employee Record")
    
    with st.form("add_new_form"):
        col1, col2, col3 = st.columns(3)
        
        # Helper for Editable Selectboxes
        def editable_box(label, col_name, key):
            opts = get_unique_opts(col_name)
            sel = st.selectbox(label, [None, NEW_FLAG] + opts, key=f"sel_{key}")
            if sel == NEW_FLAG:
                return st.text_input(f"Type New {label}", key=f"txt_{key}")
            return sel

        with col1:
            n_name = st.text_input("Employee Name*")
            n_hrms = st.text_input("HRMS ID*")
            n_unit = editable_box("Unit (Editable)", "Unit", "unit") # Unit dropdown with add new
        with col2:
            n_desig = editable_box("Designation", "Designation", "desig")
            n_stat = editable_box("Station", "STATION", "stat")
            n_pf = st.text_input("PF Number")
        with col3:
            n_pay = editable_box("Pay Level", "PAY LEVEL", "pay")
            n_basic = st.number_input("Basic Pay", value=0)
            n_pme = st.date_input("PME Due Date", value=None)

        if st.form_submit_button("✅ Save to Cloud"):
            if n_name and n_hrms:
                new_rec = clean_data({
                    "Employee Name": n_name, "HRMS ID": n_hrms, "Unit": n_unit,
                    "Designation": n_desig, "STATION": n_stat, "PF Number": n_pf,
                    "PAY LEVEL": n_pay, "BASIC PAY": n_basic, "PME DUE": str(n_pme)
                })
                db.collection(EMPLOYEE_COLLECTION).add(new_rec)
                st.success("Employee Added!"); st.cache_data.clear(); st.rerun()
            else:
                st.error("Name and HRMS ID are required.")

# --- TAB 3: EDIT/UPDATE (POORE COLUMNS) ---
with tab3:
    st.header("✏️ Edit/Update Complete Record")
    if not employee_df.empty:
        # Search employee
        search = st.selectbox("Select Employee to Edit", 
                             employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(EMPLOYEE_ID_KEY)})", axis=1))
        e_id = search.split('(')[-1].strip(')')
        record = employee_df[employee_df[EMPLOYEE_ID_KEY] == e_id].iloc[0]
        
        with st.form("update_full_form"):
            st.warning(f"Editing all 38 columns for: {search}")
            updated_data = {}
            
            # Layout in 3 columns for better visibility
            u_cols = st.columns(3)
            for i, col_name in enumerate(ALL_COLS):
                with u_cols[i % 3]:
                    old_val = record.get(col_name, "")
                    # Input for every column
                    updated_data[col_name] = st.text_input(col_name, value=str(old_val) if old_val is not None else "")
            
            if st.form_submit_button("💾 Update All Fields"):
                clean_update = clean_data(updated_data)
                db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).update(clean_update)
                st.success("Database Updated Successfully!"); st.cache_data.clear(); st.rerun()
                
        if st.button("🗑️ Permanent Delete"):
            db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).delete()
            st.cache_data.clear(); st.rerun()
    else:
        st.info("No data available to edit.")
