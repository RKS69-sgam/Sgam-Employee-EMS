import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import json

# =================================================================
# --- 0. FIREBASE SETUP & DB FUNCTIONS ---
# =================================================================

SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json' 
EMPLOYEE_COLLECTION = "employees" 
firestore = firestore

@st.cache_resource
def initialize_firebase():
    try:
        if not firebase_admin._apps:
            if st.secrets.get("firebase_config"):
                service_account_info_attrdict = st.secrets["firebase_config"]
                final_credentials = dict(service_account_info_attrdict)
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
        st.error(f"❌ Firebase Connection Failed: {e}")
        return None

db = initialize_firebase()

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
        if 'PF Number' in df.columns:
            df['PF Number'] = df['PF Number'].astype(str).fillna('')
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def clean_data_for_firestore(data):
    cleaned_data = {}
    for key, value in data.items():
        if not key or not key.strip(): continue 
        if isinstance(value, str):
            cleaned_data[key] = value.strip() if value.strip() != "" else None
        elif pd.isna(value): 
             cleaned_data[key] = None
        else:
            cleaned_data[key] = value
    return cleaned_data

def add_employee(employee_data):
    try:
        cleaned_data = clean_data_for_firestore(employee_data)
        db.collection(EMPLOYEE_COLLECTION).add(cleaned_data)
        return True 
    except Exception as e:
        st.error(f"Error adding: {e}"); return False 

def update_employee(doc_id, updated_data):
    try:
        cleaned_data = clean_data_for_firestore(updated_data)
        final_data = {k: (v if v is not None else firestore.DELETE_FIELD) for k, v in cleaned_data.items()}
        db.collection(EMPLOYEE_COLLECTION).document(doc_id).update(final_data)
        return True 
    except Exception as e:
        st.error(f"Error updating: {e}"); return False 

# =================================================================
# --- 1. STREAMLIT CONFIG & AUTH ---
# =================================================================

st.set_page_config(layout="wide", page_title="Railway HRMS Firestore")
EMPLOYEE_ID_KEY = 'HRMS ID' 
DOC_ID_KEY = 'id' 

if 'authenticated' not in st.session_state: st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.title("🔒 Login")
    USERNAME = st.secrets["app_auth"].get("username", "admin")
    PASSWORD = st.secrets["app_auth"].get("password", "Sgam@4321")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Enter"):
            if u == USERNAME and p == PASSWORD:
                st.session_state['authenticated'] = True; st.rerun()
            else: st.error("Wrong credentials")
    st.stop()

# --- Load Data ---
employee_df = get_all_employees()

# --- Tab Setup ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 वर्तमान स्थिति (Summary)", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ", "📈 रिपोर्ट"])

# ===================================================================
# --- TAB 1: SUMMARY & VIEW ---
# ===================================================================
with tab1:
    st.header("📋 डैशबोर्ड सारांश")
    if not employee_df.empty:
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("कुल कर्मचारी", len(employee_df))
        if 'Designation' in employee_df.columns:
            counts = employee_df['Designation'].value_counts()
            c2.metric("मुख्य पद", f"{counts.index[0]} ({counts.iloc[0]})")
        
        # PME Alerts
        st.subheader("⚠️ PME Due Alerts")
        if 'PME DUE' in employee_df.columns:
            pme_alerts = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")]
            if not pme_alerts.empty:
                st.dataframe(pme_alerts[['Employee Name', 'Designation', 'PME DUE']], hide_index=True)
            else: st.info("कोई PME पेंडिंग नहीं है।")

        st.divider()
        st.subheader("📝 पूरी सूची")
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY], errors='ignore'), use_container_width=True)
    else: st.info("डेटाबेस खाली है।")

# ===================================================================
# --- TAB 2: ADD EMPLOYEE (ALL COLUMNS) ---
# ===================================================================
with tab2:
    st.header("➕ नया कर्मचारी डेटा प्रविष्टि")
    with st.form("full_add_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            n_name = st.text_input("Employee Name*")
            n_id = st.text_input("HRMS ID*")
            n_pf = st.text_input("PF Number")
            n_fname = st.text_input("Father's Name")
            n_gen = st.selectbox("Gender", ["Male", "Female", "Other"])
        with col2:
            n_desig = st.text_input("Designation")
            n_stat = st.text_input("Station")
            n_unit = st.text_input("Unit")
            n_pay = st.text_input("Pay Level")
            n_basic = st.number_input("Basic Pay", value=0)
        with col3:
            n_dob = st.date_input("DOB", value=None)
            n_doa = st.date_input("DOA", value=None)
            n_dor = st.date_input("DOR", value=None)
            n_pme = st.date_input("PME DUE", value=None)
            n_med = st.text_input("Medical Category")

        st.subheader("अन्य विवरण (Other Details)")
        oa, ob, oc = st.columns(3)
        n_cug = oa.text_input("CUG Number")
        n_pran = ob.text_input("PRAN")
        n_qtr = oc.text_input("Rail Quarter No.")

        if st.form_submit_button("✅ डेटाबेस में जोड़ें"):
            if n_name and n_id:
                data = {
                    "Employee Name": n_name, "HRMS ID": n_id, "PF Number": n_pf, "FATHER'S NAME": n_fname,
                    "Gender ": n_gen, "Designation": n_desig, "STATION": n_stat, "Unit": n_unit,
                    "PAY LEVEL": n_pay, "BASIC PAY": n_basic, "DOB": str(n_dob), "DOA": str(n_doa),
                    "DOR": str(n_dor), "PME DUE": str(n_pme), "Medical category": n_med,
                    "CUG NUMBER": n_cug, "PRAN": n_pran, "RAIL QUARTER NO.": n_qtr
                }
                if add_employee(data): 
                    st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()
            else: st.error("Name and HRMS ID are mandatory!")

# ===================================================================
# --- TAB 3: UPDATE / DELETE (ALL COLUMNS) ---
# ===================================================================
with tab3:
    if not employee_df.empty:
        sel_name = st.selectbox("Select Employee to Update", 
                                employee_df.apply(lambda r: f"{r['Employee Name']} ({r[EMPLOYEE_ID_KEY]})", axis=1))
        emp_id = sel_name.split('(')[-1].strip(')')
        row = employee_df[employee_df[EMPLOYEE_ID_KEY] == emp_id].iloc[0]

        with st.form("full_update_form"):
            u1, u2, u3 = st.columns(3)
            # Pre-filling all fields
            up_name = u1.text_input("Name", value=row.get('Employee Name', ''))
            up_desig = u2.text_input("Designation", value=row.get('Designation', ''))
            up_stat = u3.text_input("Station", value=row.get('STATION', ''))
            
            up_pf = u1.text_input("PF Number", value=row.get('PF Number', ''))
            up_unit = u2.text_input("Unit", value=row.get('Unit', ''))
            up_pay = u3.text_input("Pay Level", value=row.get('PAY LEVEL', ''))
            
            up_pme = u1.text_input("PME DUE (YYYY-MM-DD)", value=row.get('PME DUE', ''))
            up_cug = u2.text_input("CUG", value=row.get('CUG NUMBER', ''))
            up_qtr = u3.text_input("Quarter No", value=row.get('RAIL QUARTER NO.', ''))

            if st.form_submit_button("✏️ अपडेट करें"):
                update_data = {
                    "Employee Name": up_name, "Designation": up_desig, "STATION": up_stat,
                    "PF Number": up_pf, "Unit": up_unit, "PAY LEVEL": up_pay,
                    "PME DUE": up_pme, "CUG NUMBER": up_cug, "RAIL QUARTER NO.": up_qtr
                }
                if update_employee(row[DOC_ID_KEY], update_data):
                    st.success("Update Successful!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ इस कर्मचारी को डिलीट करें", type="secondary"):
             db.collection(EMPLOYEE_COLLECTION).document(row[DOC_ID_KEY]).delete()
             st.success("Deleted!"); st.cache_data.clear(); st.rerun()
    else: st.info("No records to edit.")

# ===================================================================
# --- TAB 4: REPORTS ---
# ===================================================================
with tab4:
    st.header("📈 वितरण रिपोर्ट")
    if not employee_df.empty:
        c_a, c_b = st.columns(2)
        c_a.write("पद के अनुसार वितरण")
        c_a.bar_chart(employee_df['Designation'].value_counts())
        c_b.write("यूनिट के अनुसार वितरण")
        c_b.bar_chart(employee_df['Unit'].value_counts())
