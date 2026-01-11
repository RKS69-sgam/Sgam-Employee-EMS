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
# --- 1. CONFIG & AUTH ---
# =================================================================
st.set_page_config(layout="wide", page_title="Railway Management")

ADMIN_USER = "admin"
ADMIN_PASS = "Sgam@4321"

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🔒 लॉगिन (Login)")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("प्रवेश करें"):
            if u == ADMIN_USER and p == ADMIN_PASS:
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("❌ गलत विवरण")
    st.stop()

# =================================================================
# --- 2. DATA FUNCTIONS ---
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
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}"); return pd.DataFrame()

# ERROR FIX: Clean data function to remove empty keys
def clean_data_safe(data_dict):
    cleaned = {}
    for k, v in data_dict.items():
        # Check if key is not None and not an empty string
        if k and str(k).strip():
            # Value cleaning
            val = v.strip() if isinstance(v, str) else v
            cleaned[str(k).strip()] = val if val != "" else None
    return cleaned

employee_df = get_all_employees()
DOC_ID_KEY = 'id'
EMPLOYEE_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें"

# Master Column List (Fixed any trailing spaces)
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

# =================================================================
# --- 3. UI TABS ---
# =================================================================
tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ (All Columns)"])

with tab1:
    st.header("📋 वर्तमान स्थिति")
    if not employee_df.empty:
        st.metric("कुल कर्मचारी", len(employee_df))
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस खाली है।")

with tab2:
    st.header("➕ नई एंट्री")
    with st.form("add_form"):
        r1, r2, r3 = st.columns(3)
        def editable_select(label, col_name, key):
            opts = get_unique_opts(col_name)
            sel = st.selectbox(label, [None, NEW_FLAG] + opts, key=f"add_sel_{key}")
            if sel == NEW_FLAG:
                return st.text_input(f"नया {label} लिखें", key=f"add_txt_{key}")
            return sel

        n_name = r1.text_input("Name*")
        n_hrms = r1.text_input("HRMS ID*")
        n_unit = r1.selectbox("Unit", [None, NEW_FLAG] + get_unique_opts("Unit"))
        if n_unit == NEW_FLAG: n_unit = st.text_input("नई यूनिट का नाम")
        
        n_desig = r2.text_input("Designation")
        n_stat = r2.text_input("Station")
        n_pf = r2.text_input("PF Number")
        
        n_pay = r3.text_input("Pay Level")
        n_basic = r3.number_input("Basic Pay", value=0)
        n_pme = st.date_input("PME Due", value=None)

        if st.form_submit_button("✅ सुरक्षित करें"):
            if n_name and n_hrms:
                final_data = clean_data_safe({
                    "Employee Name": n_name, "HRMS ID": n_hrms, "Unit": n_unit,
                    "Designation": n_desig, "STATION": n_stat, "PF Number": n_pf,
                    "PAY LEVEL": n_pay, "BASIC PAY": n_basic, "PME DUE": str(n_pme)
                })
                db.collection(EMPLOYEE_COLLECTION).add(final_data)
                st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()

with tab3:
    st.header("✏️ पूरा रिकॉर्ड अपडेट करें")
    if not employee_df.empty:
        search_options = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(EMPLOYEE_ID_KEY)})", axis=1).tolist()
        selected = st.selectbox("कर्मचारी चुनें", search_options)
        emp_id = selected.split('(')[-1].strip(')')
        curr_rec = employee_df[employee_df[EMPLOYEE_ID_KEY] == emp_id].iloc[0]

        with st.form("update_full_form"):
            updated_vals = {}
            u_cols = st.columns(3)
            for i, col in enumerate(ALL_COLS):
                with u_cols[i % 3]:
                    current_val = curr_rec.get(col, "")
                    # Input box for each column
                    updated_vals[col] = st.text_input(col, value=str(current_val) if current_val is not None else "")
            
            if st.form_submit_button("💾 अपडेट सुरक्षित करें"):
                # SAFE UPDATE: key checking included
                final_update = clean_data_safe(updated_vals)
                if final_update:
                    db.collection(EMPLOYEE_COLLECTION).document(curr_rec[DOC_ID_KEY]).update(final_update)
                    st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
                else:
                    st.error("अपडेट करने के लिए कोई डेटा नहीं मिला।")
        
        if st.button("🗑️ रिकॉर्ड डिलीट करें"):
            db.collection(EMPLOYEE_COLLECTION).document(curr_rec[DOC_ID_KEY]).delete()
            st.success("डिलीट सफल!"); st.cache_data.clear(); st.rerun()
