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
# --- 1. CONFIG & AUTHENTICATION ---
# =================================================================
st.set_page_config(layout="wide", page_title="Railway Management System")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def login_screen():
    st.title("🔒 लॉगिन (Login)")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("प्रवेश करें"):
            if u == "admin" and p == "Sgam@4321":
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("❌ गलत यूजरनेम या पासवर्ड")

if not st.session_state['authenticated']:
    login_screen()
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

def clean_payload(raw_data):
    """ValueError: Empty element ko rokne ke liye keys aur values ko saaf karta hai"""
    clean_data = {}
    for key, val in raw_data.items():
        if key and str(key).strip(): # Sirf valid aur non-empty keys
            v_clean = str(val).strip() if val is not None else ""
            clean_data[str(key).strip()] = v_clean if v_clean != "" else None
    return clean_data

# Global Data Load
employee_df = get_all_employees()
DOC_ID_KEY = 'id'
HRMS_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें"

# Master Header List (Database Columns)
ALL_COLS = [
    'S. No.', 'PF Number', 'HRMS ID', 'Seniority No.', 'Unit', 'Employee Name', "FATHER'S NAME", 
    'Designation', 'STATION', 'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'Employee Name in Hindi', 
    'SF-11 short name', 'Gender ', 'Category', 'Designation in Hindi', 'Posting status', 
    'APPOINTMENT TYPE', 'PRMOTION DATE', 'DOR', 'Medical category', 'LAST PME', 'PME DUE', 
    'MEDICAL PLACE', 'LAST TRAINING', 'TRAINING DUE', 'SERVICE REMARK', 'EMPTYPE', 
    'PRAN', 'PENSIONACCNO', 'RAIL QUARTER NO.', 'CUG NUMBER', 'E-Number', 'UNIT No.', 
    'SICK FROM Date', 'PF No.'
]

# =================================================================
# --- 3. UI TABS ---
# =================================================================
tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ"])

# --- TAB 1: DASHBOARD & CSV DOWNLOAD ---
with tab1:
    st.header("📋 वर्तमान स्थिति")
    if not employee_df.empty:
        st.metric("कुल कर्मचारी", len(employee_df))
        
        # CSV Download (Hindi support ke sath)
        csv_data = employee_df.drop(columns=[DOC_ID_KEY], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 पूरी डेटाबेस CSV डाउनलोड करें", csv_data, "Employee_Backup.csv", "text/csv")
        
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस खाली है।")

# --- TAB 2: ADD (EDITABLE UNIT) ---
with tab2:
    st.header("➕ नई एंट्री")
    with st.form("add_form"):
        c1, c2, c3 = st.columns(3)
        n_name = c1.text_input("Employee Name*")
        n_id = c1.text_input("HRMS ID*")
        
        # Unit Editable Dropdown
        existing_units = sorted(employee_df['Unit'].dropna().unique().tolist()) if not employee_df.empty and 'Unit' in employee_df.columns else []
        n_unit_sel = c2.selectbox("Unit", [None, NEW_FLAG] + existing_units)
        n_unit = st.text_input("नयी यूनिट लिखें") if n_unit_sel == NEW_FLAG else n_unit_sel
        
        n_desig = c2.text_input("Designation")
        n_pf = c3.text_input("PF Number")
        n_pme = st.date_input("PME Due", value=None)

        if st.form_submit_button("✅ क्लाउड पर सेव करें"):
            if n_name and n_id:
                final_add = clean_payload({"Employee Name": n_name, "HRMS ID": n_id, "Unit": n_unit, "Designation": n_desig, "PF Number": n_pf, "PME DUE": str(n_pme)})
                db.collection(EMPLOYEE_COLLECTION).add(final_add)
                st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()

# --- TAB 3: UPDATE (ALL COLUMNS) ---
with tab3:
    st.header("✏️ रिकॉर्ड अपडेट करें")
    if not employee_df.empty:
        emp_list = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(HRMS_ID_KEY)})", axis=1).tolist()
        selected = st.selectbox("कर्मचारी चुनें", emp_list)
        target_id = selected.split('(')[-1].strip(')')
        record = employee_df[employee_df[HRMS_ID_KEY] == target_id].iloc[0]

        with st.form("edit_form_full"):
            st.warning(f"एडिट हो रहा है: {selected}")
            updated_data = {}
            u_cols = st.columns(3)
            
            # Saare columns ka grid
            for i, col in enumerate(ALL_COLS):
                with u_cols[i % 3]:
                    val = record.get(col, "")
                    updated_data[col] = st.text_input(col, value=str(val) if val is not None else "")

            if st.form_submit_button("💾 अपडेट सुरक्षित करें"):
                final_up = clean_payload(updated_data)
                if final_up:
                    db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).update(final_up)
                    st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ डिलीट करें"):
            db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).delete()
            st.success("डिलीट सफल!"); st.cache_data.clear(); st.rerun()
