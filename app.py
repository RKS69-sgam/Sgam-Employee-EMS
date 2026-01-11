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
# --- 1. CONFIG & AUTHENTICATION (admin / Sgam@4321) ---
# =================================================================
st.set_page_config(layout="wide", page_title="Railway Management System")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🔒 लॉगिन (Login)")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("प्रवेश करें"):
            if u == "admin" and p == "Sgam@4321":
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("❌ गलत विवरण")
    st.stop()

# =================================================================
# --- 2. DATA & CLEANING UTILITIES ---
# =================================================================
def get_data():
    if db is None: return pd.DataFrame()
    docs = db.collection(EMPLOYEE_COLLECTION).stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        data.append(d)
    return pd.DataFrame(data)

def clean_payload(raw_dict):
    """ValueError: Empty element aur Unnamed columns ko hatane ke liye"""
    clean = {}
    for k, v in raw_dict.items():
        ks = str(k).strip()
        if ks and not ks.startswith('Unnamed'):
            val = str(v).strip() if v is not None else ""
            clean[ks] = val if val != "" else None
    return clean

# Aapki file ke exact 38+ headers
ALL_COLS = [
    'S. No.', 'Employee Name', 'Employee Name in Hindi', 'HRMS ID', 'PF Number', 
    'FATHER\'S NAME', 'Designation', 'Designation in Hindi', 'Unit', 'STATION', 
    'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'DOR', 'Seniority No.', 'Category', 
    'Medical category', 'PME DUE', 'LAST PME', 'TRAINING DUE', 'LAST TRAINING', 
    'PRMOTION DATE', 'PRAN', 'Gender ', 'CUG NUMBER', 'RAIL QUARTER NO.', 
    'Posting status', 'APPOINTMENT TYPE', 'EMPTYPE', 'PENSIONACCNO', 'E-Number', 
    'UNIT No.', 'SICK FROM Date', 'SERVICE REMARK', 'MEDICAL PLACE', 'SF-11 short name'
]

employee_df = get_data()
NEW_FLAG = "➕ नया दर्ज करें"

def get_opts(col):
    if not employee_df.empty and col in employee_df.columns:
        return sorted([str(x) for x in employee_df[col].unique() if str(x).strip() != 'nan' and str(x).strip() != ""])
    return []

# =================================================================
# --- 3. UI TABS ---
# =================================================================
tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ"])

# --- TAB 1: DASHBOARD ---
with tab1:
    st.header("📋 मास्टर डेटाबेस")
    if not employee_df.empty:
        csv = employee_df.drop(columns=['id'], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 डेटाबेस बैकअप डाउनलोड (CSV)", csv, "Railway_DB.csv", "text/csv")
        st.dataframe(employee_df.drop(columns=['id'], errors='ignore'), use_container_width=True)
    else:
        st.info("डेटाबेस खाली है।")

# --- TAB 2: ADD NEW (38 COLUMNS & DROPDOWNS) ---
with tab2:
    st.header("➕ नए कर्मचारी की एंट्री")
    with st.form("new_emp_form"):
        new_data = {}
        cols = st.columns(3)
        
        # Dropdown configuration
        drop_fields = {
            'STATION': get_opts('STATION'),
            'Unit': get_opts('Unit'),
            'Designation': get_opts('Designation'),
            'Gender ': ['पुरूष', 'महिला', 'अन्य'],
            'Category': get_opts('Category'),
            'Medical category': get_opts('Medical category')
        }

        for i, c_name in enumerate(ALL_COLS):
            with cols[i % 3]:
                if c_name in drop_fields:
                    sel = st.selectbox(f"{c_name}", [None, NEW_FLAG] + drop_fields[c_name], key=f"add_{c_name}")
                    if sel == NEW_FLAG:
                        new_data[c_name] = st.text_input(f"नया {c_name} यहाँ लिखें", key=f"add_new_txt_{c_name}")
                    else:
                        new_data[c_name] = sel
                else:
                    new_data[c_name] = st.text_input(c_name, key=f"add_txt_{c_name}")

        if st.form_submit_button("✅ डेटाबेस में सुरक्षित करें"):
            if new_data.get('Employee Name') and new_data.get('HRMS ID'):
                db.collection(EMPLOYEE_COLLECTION).add(clean_payload(new_data))
                st.success("सफलतापूर्वक जोड़ा गया!"); st.rerun()
            else:
                st.error("Name और HRMS ID जरूरी हैं।")

# --- TAB 3: UPDATE & DELETE (WITH REFRESH FIX) ---
with tab3:
    st.header("✏️ रिकॉर्ड अपडेट या डिलीट")
    if not employee_df.empty:
        # Step 1: Employee Select
        names = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get('HRMS ID')})", axis=1).tolist()
        selected_emp = st.selectbox("कर्मचारी खोजें", names)
        
        # Step 2: Extract details
        h_id = selected_emp.split('(')[-1].strip(')')
        rec = employee_df[employee_df['HRMS ID'] == h_id].iloc[0]
        doc_id = rec['id']

        # Step 3: Update Form (KEY fix added here for instant refresh)
        with st.form(key=f"up_form_{h_id}"):
            st.warning(f"Editing Mode: {selected_emp}")
            up_vals = {}
            u_cols = st.columns(3)
            
            for i, col in enumerate(ALL_COLS):
                with u_cols[i % 3]:
                    val = rec.get(col, "")
                    # Unique key for each input based on employee HRMS ID
                    up_vals[col] = st.text_input(col, value=str(val) if val is not None else "", key=f"f_{h_id}_{col}")
            
            if st.form_submit_button("💾 अपडेट सुरक्षित करें"):
                db.collection(EMPLOYEE_COLLECTION).document(doc_id).update(clean_payload(up_vals))
                st.success("डेटा अपडेट हो गया!"); st.rerun()

        # Step 4: Delete Option
        st.write("---")
        st.subheader("⚠️ खतरनाक क्षेत्र")
        if st.button(f"🗑️ {selected_emp} का रिकॉर्ड डिलीट करें", type="secondary"):
            db.collection(EMPLOYEE_COLLECTION).document(doc_id).delete()
            st.error("रिकॉर्ड हमेशा के लिए हटा दिया गया।")
            st.rerun()
