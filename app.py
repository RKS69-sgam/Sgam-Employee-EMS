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
        st.error(f"❌ Firebase Error: {e}")
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
        st.error(f"Error: {e}"); return pd.DataFrame()

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

# =================================================================
# --- 1. CONFIG & AUTH ---
# =================================================================

st.set_page_config(layout="wide", page_title="Railway Management")
EMPLOYEE_ID_KEY = 'HRMS ID' 
DOC_ID_KEY = 'id' 
NEW_FLAG = "➕ नया दर्ज करें"

if 'authenticated' not in st.session_state: st.session_state['authenticated'] = False
if not st.session_state['authenticated']:
    st.title("🔒 Login")
    with st.form("login"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Enter"):
            if u == st.secrets["app_auth"]["username"] and p == st.secrets["app_auth"]["password"]:
                st.session_state['authenticated'] = True; st.rerun()
    st.stop()

# --- Load Data & Options ---
employee_df = get_all_employees()

def get_opts(col):
    if not employee_df.empty and col in employee_df.columns:
        return sorted([str(x) for x in employee_df[col].dropna().unique() if str(x).strip() != ""])
    return []

# --- Tab Setup ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 वर्तमान स्थिति", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ", "📈 रिपोर्ट"])

# ===================================================================
# --- TAB 1: SUMMARY & VIEW ---
# ===================================================================
with tab1:
    st.header("📋 कर्मचारी सारांश (Summary Dashboard)")
    if not employee_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("कुल कर्मचारी", len(employee_df))
        if 'Designation' in employee_df.columns:
            counts = employee_df['Designation'].value_counts()
            c2.metric("मुख्य पद", f"{counts.index[0]} ({counts.iloc[0]})")
        
        st.subheader("⚠️ PME Due Alerts")
        if 'PME DUE' in employee_df.columns:
            pme_list = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")]
            st.dataframe(pme_list[['Employee Name', 'Designation', 'PME DUE']], hide_index=True)
        
        st.divider()
        st.subheader("📝 पूरी सूची")
        st.dataframe(employee_df.drop(columns=[DOC_ID_KEY]), use_container_width=True)
    else: st.info("डेटाबेस खाली है।")

# ===================================================================
# --- TAB 2: ADD (ALL COLUMNS WITH DROPDOWNS) ---
# ===================================================================
with tab2:
    st.header("➕ नया कर्मचारी जोड़ें")
    with st.form("add_full"):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_name = st.text_input("Name*")
            n_hrms = st.text_input("HRMS ID*")
            # Dropdown for Designation
            d_sel = st.selectbox("Designation", [None, NEW_FLAG] + get_opts('Designation'))
            n_desig = st.text_input("Enter New Designation") if d_sel == NEW_FLAG else d_sel
        with c2:
            n_pf = st.text_input("PF Number")
            # Dropdown for Station
            s_sel = st.selectbox("Station", [None, NEW_FLAG] + get_opts('STATION'))
            n_stat = st.text_input("Enter New Station") if s_sel == NEW_FLAG else s_sel
            # Dropdown for Unit
            u_sel = st.selectbox("Unit", [None, NEW_FLAG] + get_opts('Unit'))
            n_unit = st.text_input("Enter New Unit") if u_sel == NEW_FLAG else u_sel
        with c3:
            # Dropdown for Pay Level
            p_sel = st.selectbox("Pay Level", [None, NEW_FLAG] + get_opts('PAY LEVEL'))
            n_pay = st.text_input("Enter New Pay Level") if p_sel == NEW_FLAG else p_sel
            n_basic = st.number_input("Basic Pay", value=0)
            n_pme = st.date_input("PME DUE", value=None)

        st.subheader("अतिरिक्त विवरण (Additional Details)")
        a1, a2, a3 = st.columns(3)
        n_fname = a1.text_input("Father's Name")
        n_dob = a1.date_input("DOB", value=None)
        n_doa = a2.date_input("DOA", value=None)
        n_dor = a2.date_input("DOR", value=None)
        n_med = a3.text_input("Medical Category")
        n_cug = a3.text_input("CUG Number")

        if st.form_submit_button("✅ डेटाबेस में जोड़ें"):
            if n_name and n_hrms:
                data = clean_data_for_firestore({
                    "Employee Name": n_name, "HRMS ID": n_hrms, "PF Number": n_pf,
                    "Designation": n_desig, "STATION": n_stat, "Unit": n_unit,
                    "PAY LEVEL": n_pay, "BASIC PAY": n_basic, "PME DUE": str(n_pme),
                    "FATHER'S NAME": n_fname, "DOB": str(n_dob), "DOA": str(n_doa),
                    "DOR": str(n_dor), "Medical category": n_med, "CUG NUMBER": n_cug
                })
                db.collection(EMPLOYEE_COLLECTION).add(data)
                st.success("Added!"); st.cache_data.clear(); st.rerun()
            else: st.error("Name & HRMS ID required")

# ===================================================================
# --- TAB 3: UPDATE (ALL COLUMNS WITH DROPDOWNS) ---
# ===================================================================
with tab3:
    if not employee_df.empty:
        sel = st.selectbox("Select Employee", employee_df.apply(lambda r: f"{r['Employee Name']} ({r[EMPLOYEE_ID_KEY]})", axis=1))
        row = employee_df[employee_df[EMPLOYEE_ID_KEY] == sel.split('(')[-1].strip(')')].iloc[0]

        with st.form("edit_full"):
            u1, u2, u3 = st.columns(3)
            # Designation Dropdown in Update
            d_up_sel = u1.selectbox("Update Designation", [row.get('Designation'), NEW_FLAG] + get_opts('Designation'))
            up_desig = u1.text_input("New Designation") if d_up_sel == NEW_FLAG else d_up_sel
            
            # Station Dropdown in Update
            s_up_sel = u2.selectbox("Update Station", [row.get('STATION'), NEW_FLAG] + get_opts('STATION'))
            up_stat = u2.text_input("New Station") if s_up_sel == NEW_FLAG else s_up_sel
            
            # Unit Dropdown in Update
            u_up_sel = u3.selectbox("Update Unit", [row.get('Unit'), NEW_FLAG] + get_opts('Unit'))
            up_unit = u3.text_input("New Unit") if u_up_sel == NEW_FLAG else u_up_sel

            # Other Fields
            up_name = u1.text_input("Name", value=row.get('Employee Name', ''))
            up_pme = u2.text_input("PME DUE (YYYY-MM-DD)", value=row.get('PME DUE', ''))
            up_basic = u3.text_input("Basic Pay", value=str(row.get('BASIC PAY', '0')))
            
            if st.form_submit_button("✏️ अपडेट करें"):
                up_data = clean_data_for_firestore({
                    "Employee Name": up_name, "Designation": up_desig, 
                    "STATION": up_stat, "Unit": up_unit, "PME DUE": up_pme, "BASIC PAY": up_basic
                })
                db.collection(EMPLOYEE_COLLECTION).document(row[DOC_ID_KEY]).update(up_data)
                st.success("Updated!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ हटाएँ"):
            db.collection(EMPLOYEE_COLLECTION).document(row[DOC_ID_KEY]).delete()
            st.success("Deleted!"); st.cache_data.clear(); st.rerun()

# ===================================================================
# --- TAB 4: REPORTS ---
# ===================================================================
with tab4:
    st.header("📈 पद और यूनिट विश्लेषण")
    if not employee_df.empty:
        st.bar_chart(employee_df['Designation'].value_counts())
        st.write(employee_df['Unit'].value_counts())
