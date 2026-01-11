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
# --- 1. AUTHENTICATION (admin / Sgam@4321) ---
# =================================================================
st.set_page_config(layout="wide", page_title="Railway Management System")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🔒 लॉगिन (Login)")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Enter"):
            if u == "admin" and p == "Sgam@4321":
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("❌ Invalid Credentials")
    st.stop()

# =================================================================
# --- 2. DATA UTILITIES ---
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
        st.error(f"Error fetching data: {e}"); return pd.DataFrame()

def clean_payload(raw_data):
    """Khaali keys ko filter karta hai taki Firestore error na aaye"""
    clean_data = {}
    for key, val in raw_data.items():
        if key and str(key).strip() and not str(key).startswith('Unnamed'):
            v_str = str(val).strip() if val is not None else ""
            clean_data[str(key).strip()] = v_str if v_str != "" else None
    return clean_data

# Global Data
employee_df = get_all_employees()
DOC_ID_KEY = 'id'
HRMS_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें"

# Aapki Excel file ke exact headers
ALL_COLS = [
    'S. No.', 'Employee Name', 'Employee Name in Hindi', 'HRMS ID', 'PF Number', 
    'FATHER\'S NAME', 'Designation', 'Designation in Hindi', 'Unit', 'STATION', 
    'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'DOR', 'Seniority No.', 'Category', 
    'Medical category', 'PME DUE', 'LAST PME', 'TRAINING DUE', 'LAST TRAINING', 
    'PRMOTION DATE', 'PRAN', 'Gender ', 'CUG NUMBER', 'RAIL QUARTER NO.', 
    'Posting status', 'APPOINTMENT TYPE', 'EMPTYPE', 'PENSIONACCNO', 'E-Number', 
    'UNIT No.', 'SICK FROM Date', 'SERVICE REMARK', 'MEDICAL PLACE', 'SF-11 short name'
]

# =================================================================
# --- 3. UI TABS ---
# =================================================================
tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ"])

# --- TAB 1: DASHBOARD ---
with tab1:
    st.header("📋 मास्टर डेटाबेस")
    if not employee_df.empty:
        # Excel Download Button
        csv_file = employee_df.drop(columns=[DOC_ID_KEY], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 पूरी डेटाबेस CSV डाउनलोड करें", csv_file, "Employee_Export.csv", "text/csv")
        
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस खाली है।")

# --- TAB 2: ADD NEW ---
with tab2:
    st.header("➕ नई एंट्री")
    with st.form("add_new"):
        c1, c2, c3 = st.columns(3)
        n_name = c1.text_input("Employee Name*")
        n_id = c1.text_input("HRMS ID*")
        
        # Editable Unit Dropdown
        u_list = sorted(employee_df['Unit'].dropna().unique().tolist()) if not employee_df.empty else []
        u_sel = c2.selectbox("Unit", [None, NEW_FLAG] + u_list)
        n_unit = st.text_input("नयी यूनिट का नाम") if u_sel == NEW_FLAG else u_sel
        
        n_desig = c2.text_input("Designation")
        n_pf = c3.text_input("PF Number")
        n_pme = st.date_input("PME Due Date", value=None)

        if st.form_submit_button("✅ सुरक्षित करें"):
            if n_name and n_id:
                final_add = clean_payload({
                    "Employee Name": n_name, "HRMS ID": n_id, "Unit": n_unit,
                    "Designation": n_desig, "PF Number": n_pf, "PME DUE": str(n_pme)
                })
                db.collection(EMPLOYEE_COLLECTION).add(final_add)
                st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()
            else:
                st.error("Name और HRMS ID जरूरी हैं।")

# --- TAB 3: UPDATE (FIXED ERROR) ---
with tab3:
    st.header("✏️ रिकॉर्ड अपडेट")
    if not employee_df.empty:
        # Search Box
        options = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(HRMS_ID_KEY)})", axis=1).tolist()
        emp_sel = st.selectbox("कर्मचारी चुनें", options)
        e_id = emp_sel.split('(')[-1].strip(')')
        record = employee_df[employee_df[HRMS_ID_KEY] == e_id].iloc[0]

        with st.form("update_form"):
            st.info(f"Editing: {emp_sel}")
            updated_vals = {}
            u_grid = st.columns(3)
            
            # Show all 37+ columns from your database headers
            for i, col in enumerate(ALL_COLS):
                with u_grid[i % 3]:
                    current_val = record.get(col, "")
                    updated_vals[col] = st.text_input(col, value=str(current_val) if current_val is not None else "")

            if st.form_submit_button("💾 अपडेट सुरक्षित करें"):
                # SAFE UPDATE: key checking included
                final_up = clean_payload(updated_vals)
                if final_up:
                    # FIXED: Yahan variable name 'final_up' kar diya hai jo pehle 'final_payload' tha
                    db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).update(final_up)
                    st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
                else:
                    st.error("अपडेट करने के लिए कोई डेटा नहीं मिला।")
        
        if st.button("🗑️ रिकॉर्ड डिलीट करें"):
            db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).delete()
            st.success("Deleted!"); st.cache_data.clear(); st.rerun()
