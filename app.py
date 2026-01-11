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
    return {k: (v.strip() if isinstance(v, str) and v.strip() != "" else v) for k, v in data.items() if k}

# =================================================================
# --- 2. APP CONFIG & AUTH ---
# =================================================================

st.set_page_config(layout="wide", page_title="Railway HRMS")
EMPLOYEE_ID_KEY = 'HRMS ID' 
DOC_ID_KEY = 'id' 
NEW_FLAG = "➕ नया दर्ज करें (Add New)"

# Columns List based on your database structure
ALL_COLS = [
    'S. No.', 'PF Number', EMPLOYEE_ID_KEY, 'Seniority No.', 'Unit', 'Employee Name', 'FATHER\'S NAME', 
    'Designation', 'STATION', 'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'Employee Name in Hindi', 
    'SF-11 short name', 'Gender ', 'Category', 'Designation in Hindi', 'Posting status', 
    'APPOINTMENT TYPE', 'PRMOTION DATE', 'DOR', 'Medical category', 'LAST PME', 'PME DUE', 
    'MEDICAL PLACE', 'LAST TRAINING', 'TRAINING DUE', 'SERVICE REMARK', 'EMPTYPE', 
    'PRAN', 'PENSIONACCNO', 'RAIL QUARTER NO.', 'CUG NUMBER', 'E-Number', 'UNIT No.', 
    'SICK FROM Date', 'PF No.'
]

if 'authenticated' not in st.session_state: st.session_state['authenticated'] = False
if not st.session_state['authenticated']:
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if u == st.secrets["app_auth"]["username"] and p == st.secrets["app_auth"]["password"]:
                st.session_state['authenticated'] = True; st.rerun()
    st.stop()

employee_df = get_all_employees()

def get_unique_opts(col_name):
    if not employee_df.empty and col_name in employee_df.columns:
        return sorted([str(x) for x in employee_df[col_name].dropna().unique() if str(x).strip() != ""])
    return []

tab1, tab2, tab3 = st.tabs(["📊 वर्तमान स्थिति", "➕ नया कर्मचारी जोड़ें", "✏️ अपडेट/हटाएँ"])

# ===================================================================
# --- TAB 1: SUMMARY ---
# ===================================================================
with tab1:
    st.header("📋 कर्मचारी डैशबोर्ड")
    if not employee_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("कुल कर्मचारी", len(employee_df))
        
        st.subheader("⚠️ PME Due List")
        if 'PME DUE' in employee_df.columns:
            pme_due_df = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")]
            st.dataframe(pme_due_df[['Employee Name', 'Designation', 'PME DUE']], hide_index=True)
            
        st.divider()
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else: st.info("डेटा उपलब्ध नहीं है।")

# ===================================================================
# --- TAB 2: ADD (EDITABLE DROPDOWNS) ---
# ===================================================================
with tab2:
    st.header("➕ नया कर्मचारी डेटा प्रविष्टि")
    with st.form("add_form"):
        col1, col2, col3 = st.columns(3)
        
        # Helper for Editable Dropdowns
        def editable_select(label, col_name, key_prefix):
            opts = get_unique_opts(col_name)
            sel = st.selectbox(label, [None, NEW_FLAG] + opts, key=f"{key_prefix}_sel")
            if sel == NEW_FLAG:
                return st.text_input(f"नया {label} दर्ज करें", key=f"{key_prefix}_text")
            return sel

        with col1:
            name = st.text_input("Employee Name*")
            hrms = st.text_input("HRMS ID*")
            desig = editable_select("Designation", "Designation", "add_desig")
        with col2:
            unit = editable_select("Unit", "Unit", "add_unit")
            station = editable_select("Station", "STATION", "add_stat")
            pf = st.text_input("PF Number")
        with col3:
            pay_lvl = editable_select("Pay Level", "PAY LEVEL", "add_pay")
            basic = st.number_input("Basic Pay", value=0)
            pme = st.date_input("PME Due Date", value=None)

        st.subheader("अन्य सभी विवरण (Other Details)")
        o1, o2, o3 = st.columns(3)
        # Baki bache saare columns yahan cover honge
        f_name = o1.text_input("Father's Name")
        dob = o1.date_input("DOB", value=None)
        doa = o2.date_input("DOA", value=None)
        dor = o2.date_input("DOR", value=None)
        med_cat = o3.text_input("Medical Category")
        cug = o3.text_input("CUG Number")
        pran = o3.text_input("PRAN")

        if st.form_submit_button("✅ सुरक्षित करें"):
            if name and hrms:
                new_data = clean_data({
                    "Employee Name": name, "HRMS ID": hrms, "Designation": desig,
                    "Unit": unit, "STATION": station, "PF Number": pf, 
                    "PAY LEVEL": pay_lvl, "BASIC PAY": basic, "PME DUE": str(pme),
                    "FATHER'S NAME": f_name, "DOB": str(dob), "DOA": str(doa), 
                    "DOR": str(dor), "Medical category": med_cat, "CUG NUMBER": cug, "PRAN": pran
                })
                db.collection(EMPLOYEE_COLLECTION).add(new_data)
                st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()
            else: st.error("नाम और HRMS ID जरूरी हैं।")

# ===================================================================
# --- TAB 3: UPDATE (ALL COLUMNS) ---
# ===================================================================
with tab3:
    st.header("✏️ कर्मचारी विवरण अपडेट करें")
    if not employee_df.empty:
        # Selection for Update
        search_list = employee_df.apply(lambda r: f"{r['Employee Name']} ({r[EMPLOYEE_ID_KEY]})", axis=1).tolist()
        selected_emp = st.selectbox("अपडेट के लिए चुनें", search_list)
        emp_id = selected_emp.split('(')[-1].strip(')')
        curr_row = employee_df[employee_df[EMPLOYEE_ID_KEY] == emp_id].iloc[0]

        with st.form("update_form_full"):
            st.info(f"आप {emp_id} का डेटा एडिट कर रहे हैं। सभी फ़ील्ड्स नीचे उपलब्ध हैं।")
            
            # Dinamic Columns Generation (Saare columns ko grid mein dikhana)
            updated_values = {}
            cols = st.columns(3)
            for idx, col_name in enumerate(ALL_COLS):
                if col_name == DOC_ID_KEY: continue
                # Har column ko uske index ke hisab se 3 columns mein distribute karna
                with cols[idx % 3]:
                    val = curr_row.get(col_name, "")
                    # Date fields ke liye text input hi rakha hai takki editing asan ho
                    updated_values[col_name] = st.text_input(col_name, value=str(val) if val is not None else "")

            if st.form_submit_button("✏️ डेटाबेस अपडेट करें"):
                final_update = clean_data(updated_values)
                db.collection(EMPLOYEE_COLLECTION).document(curr_row[DOC_ID_KEY]).update(final_update)
                st.success("डेटा अपडेट हो गया!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ इस कर्मचारी को डिलीट करें", type="secondary"):
            db.collection(EMPLOYEE_COLLECTION).document(curr_row[DOC_ID_KEY]).delete()
            st.success("हटा दिया गया!"); st.cache_data.clear(); st.rerun()
    else:
        st.info("कोई डेटा नहीं मिला।")
