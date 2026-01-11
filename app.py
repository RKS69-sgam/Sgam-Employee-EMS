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

# Login State Check
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def login_screen():
    st.title("🔒 लॉगिन (Login)")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("प्रवेश करें"):
            # Credentials set to: admin / Sgam@4321
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

def clean_update_payload(raw_data):
    """Khaali keys aur null values ko saaf karta hai taki error na aaye"""
    clean_payload = {}
    for key, val in raw_data.items():
        if key and str(key).strip(): # Sirf valid field names bhejta hai
            v_clean = val.strip() if isinstance(val, str) else val
            clean_payload[str(key).strip()] = v_clean if v_clean != "" else None
    return clean_payload

# Global Variables
employee_df = get_all_employees()
DOC_ID_KEY = 'id'
EMPLOYEE_ID_KEY = 'HRMS ID'
NEW_FLAG = "➕ नया दर्ज करें"

# Database Columns (Header List)
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
tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ"])

# --- TAB 1: DASHBOARD & DOWNLOAD ---
with tab1:
    st.header("📋 वर्तमान स्थिति")
    if not employee_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("कुल कर्मचारी", len(employee_df))
        
        # PME Alerts
        if 'PME DUE' in employee_df.columns:
            st.subheader("⚠️ PME Due Alerts")
            pme_df = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")]
            st.dataframe(pme_df[['Employee Name', 'Designation', 'PME DUE']], hide_index=True)
        
        st.divider()
        st.subheader("📥 डेटाबेस डाउनलोड")
        # Hindi Support ke liye utf-8-sig encoding use ki hai
        csv_data = employee_df.drop(columns=[DOC_ID_KEY], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("Puri List CSV Download Karein", csv_data, "Employee_DB.csv", "text/csv")
        
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस खाली है।")

# --- TAB 2: ADD (EDITABLE DROPDOWNS) ---
with tab2:
    st.header("➕ नई कर्मचारी प्रविष्टि")
    with st.form("add_form"):
        r1, r2, r3 = st.columns(3)
        
        n_name = r1.text_input("Name*")
        n_hrms = r1.text_input("HRMS ID*")
        
        # Unit Dropdown with Edit/Add New feature
        n_unit_sel = r1.selectbox("Unit", [None, NEW_FLAG] + get_unique_opts("Unit"))
        n_unit = st.text_input("नयी यूनिट लिखें") if n_unit_sel == NEW_FLAG else n_unit_sel
        
        n_desig = r2.text_input("Designation")
        n_stat = r2.text_input("Station")
        n_pf = r2.text_input("PF Number")
        
        n_pay = r3.text_input("Pay Level")
        n_basic = r3.number_input("Basic Pay", value=0)
        n_pme = r3.date_input("PME Due Date", value=None)

        if st.form_submit_button("✅ क्लाउड पर सेव करें"):
            if n_name and n_hrms:
                final_data = clean_update_payload({
                    "Employee Name": n_name, "HRMS ID": n_hrms, "Unit": n_unit,
                    "Designation": n_desig, "STATION": n_stat, "PF Number": n_pf,
                    "PAY LEVEL": n_pay, "BASIC PAY": n_basic, "PME DUE": str(n_pme)
                })
                db.collection(EMPLOYEE_COLLECTION).add(final_data)
                st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()
            else:
                st.error("Name और HRMS ID जरूरी हैं।")

# --- TAB 3: UPDATE (ALL 38 COLUMNS) ---
with tab3:
    st.header("✏️ पूरा रिकॉर्ड एडिट करें")
    if not employee_df.empty:
        search_list = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get(EMPLOYEE_ID_KEY)})", axis=1).tolist()
        selected = st.selectbox("कर्मचारी चुनें", search_list)
        emp_id = selected.split('(')[-1].strip(')')
        curr_row = employee_df[employee_df[EMPLOYEE_ID_KEY] == emp_id].iloc[0]

        with st.form("full_update"):
            st.warning(f"एडिट हो रहा है: {selected}")
            updated_vals = {}
            u_cols = st.columns(3)
            
            # loop for all database columns
            for i, col in enumerate(ALL_COLS):
                with u_cols[i % 3]:
                    old_val = curr_row.get(col, "")
                    updated_vals[col] = st.text_input(col, value=str(old_val) if old_val is not None else "")
            
            if st.form_submit_button("💾 अपडेट सुरक्षित करें"):
                # ERROR FIX: Safe payload cleaning
                final_payload = clean_update_payload(updated_vals)
                if final_payload:
                    db.collection(EMPLOYEE_COLLECTION).document(curr_row[DOC_ID_KEY]).update(final_payload)
                    st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
                else:
                    st.error("कोई डेटा अपडेट नहीं हुआ।")
        
        if st.button("🗑️ रिकॉर्ड डिलीट करें"):
            db.collection(EMPLOYEE_COLLECTION).document(curr_row[DOC_ID_KEY]).delete()
            st.success("डिलीट सफल!"); st.cache_data.clear(); st.rerun()
    else:
        st.info("संपादन के लिए कोई डेटा नहीं है।")
