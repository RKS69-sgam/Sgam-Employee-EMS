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
st.set_page_config(layout="wide", page_title="Railway Employee System")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🔒 लॉगिन (Login)")
    with st.form("login"):
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
    """Khaali keys aur formats ko saaf karta hai taki Firestore error na de"""
    clean_data = {}
    for key, val in raw_data.items():
        # Check if key is valid (not empty string)
        if key and str(key).strip() and not str(key).startswith('Unnamed'):
            v_str = str(val).strip() if val is not None else ""
            # Agar value khaali hai toh None (null) bhejein
            clean_data[str(key).strip()] = v_str if v_str != "" else None
    return clean_data

# Global Variables
employee_df = get_all_employees()
DOC_ID_KEY = 'id'
HRMS_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें"

# Exact Headers from your CSV
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

# --- TAB 1: VIEW & DOWNLOAD ---
with tab1:
    st.header("📋 मास्टर डेटाबेस")
    if not employee_df.empty:
        # CSV Download Logic
        csv_file = employee_df.drop(columns=[DOC_ID_KEY], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 डाउनलोड Excel (CSV)", csv_file, "Employee_Export.csv", "text/csv")
        
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस में कोई रिकॉर्ड नहीं है।")

# --- TAB 2: ADD NEW (EDITABLE UNIT) ---
with tab2:
    st.header("➕ नए कर्मचारी का विवरण भरें")
    with st.form("add_new"):
        c1, c2, c3 = st.columns(3)
        
        name = c1.text_input("Employee Name*")
        hrms = c1.text_input("HRMS ID*")
        
        # Unit Dropdown + Add New
        u_list = sorted(employee_df['Unit'].dropna().unique().tolist()) if not employee_df.empty else []
        u_sel = c2.selectbox("Unit", [None, NEW_FLAG] + u_list)
        unit = st.text_input("नई यूनिट का नाम") if u_sel == NEW_FLAG else u_sel
        
        desig = c2.text_input("Designation")
        stat = c3.text_input("STATION")
        pf = c3.text_input("PF Number")
        
        st.write("---")
        dob = st.date_input("Date of Birth (DOB)", value=None)
        pme = st.date_input("PME Due Date", value=None)

        if st.form_submit_button("✅ सुरक्षित करें"):
            if name and hrms:
                new_rec = clean_payload({
                    "Employee Name": name, "HRMS ID": hrms, "Unit": unit,
                    "Designation": desig, "STATION": stat, "PF Number": pf,
                    "DOB": str(dob), "PME DUE": str(pme)
                })
                db.collection(EMPLOYEE_COLLECTION).add(new_rec)
                st.success("Record Saved!"); st.cache_data.clear(); st.rerun()
            else:
                st.error("Name aur HRMS ID अनिवार्य हैं।")

# --- TAB 3: UPDATE (GRID OF ALL 38 COLUMNS) ---
with tab3:
    st.header("✏️ रिकॉर्ड अपडेट या डिलीट करें")
    if not employee_df.empty:
        # Search & Select
        options = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(HRMS_ID_KEY)})", axis=1).tolist()
        emp_sel = st.selectbox("कर्मचारी खोजें", options)
        e_id = emp_sel.split('(')[-1].strip(')')
        record = employee_df[employee_df[HRMS_ID_KEY] == e_id].iloc[0]

        with st.form("update_form"):
            st.info(f"Editing: {emp_sel}")
            updated_vals = {}
            u_grid = st.columns(3)
            
            # Aapki file ke saare headers yahan loop mein dikhenge
            for i, col in enumerate(ALL_COLS):
                with u_grid[i % 3]:
                    old_val = record.get(col, "")
                    updated_vals[col] = st.text_input(col, value=str(old_val) if old_val is not None else "")

            if st.form_submit_button("💾 सभी बदलाव अपडेट करें"):
                final_up = clean_payload(updated_vals)
                if final_up:
                    db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).update(final_payload)
                    st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ कर्मचारी का नाम डेटाबेस से हटाएं"):
            db.collection(EMPLOYEE_COLLECTION).document(record[DOC_ID_KEY]).delete()
            st.success("Deleted!"); st.cache_data.clear(); st.rerun()
