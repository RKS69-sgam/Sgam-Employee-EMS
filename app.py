import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import json
import re

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
        st.error(f"❌ Firebase कनेक्शन विफल। त्रुटि: {e}")
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
        st.error(f"डेटा लाने में त्रुटि: {e}")
        return pd.DataFrame()

def clean_data_for_firestore(data):
    cleaned_data = {}
    for key, value in data.items():
        if not key or not key.strip():
            continue 
        if isinstance(value, str):
            if value.strip() == "":
                cleaned_data[key] = None
            else:
                cleaned_data[key] = value.strip()
        elif pd.isna(value): 
             cleaned_data[key] = None
        else:
            cleaned_data[key] = value
    return cleaned_data

def add_employee(employee_data):
    if db:
        try:
            cleaned_data = clean_data_for_firestore(employee_data)
            db.collection(EMPLOYEE_COLLECTION).add(cleaned_data)
            return True 
        except Exception as e:
            st.error(f"नया रिकॉर्ड जोड़ने में त्रुटि: {e}")
            return False 

def update_employee(firestore_doc_id, updated_data):
    if db:
        try:
            cleaned_data = clean_data_for_firestore(updated_data)
            final_update_data = {}
            for key, value in cleaned_data.items():
                if value is None:
                    final_update_data[key] = firestore.DELETE_FIELD
                else:
                    final_update_data[key] = value
            if not final_update_data:
                 return True
            doc_ref = db.collection(EMPLOYEE_COLLECTION).document(firestore_doc_id)
            doc_ref.update(final_update_data) 
            return True 
        except Exception as e:
            st.error(f"रिकॉर्ड अपडेट करने में त्रुटि: {e}")
            return False 
    return False

def delete_employee(firestore_doc_id):
    if db:
        try:
            db.collection(EMPLOYEE_COLLECTION).document(firestore_doc_id).delete()
            return True
        except Exception as e:
            st.error(f"रिकॉर्ड हटाने में त्रुटि: {e}")
            return False
    return False

# =================================================================
# --- 1. STREAMLIT APP START ---
# =================================================================

st.set_page_config(layout="wide", page_title="कर्मचारी प्रबंधन प्रणाली (Firestore)")
EMPLOYEE_ID_KEY = 'HRMS ID' 
DOC_ID_KEY = 'id' 

def login_form():
    st.title("🔒 लॉगिन आवश्यक")
    if 'app_auth' not in st.secrets:
        st.error("❌ 'app_auth' Secrets में नहीं मिला।")
        st.stop()
    USERNAME = st.secrets["app_auth"].get("username", "admin")
    PASSWORD = st.secrets["app_auth"].get("password", "Sgam@4321") 
    with st.form("login_form"):
        username_input = st.text_input("यूजरनेम")
        password_input = st.text_input("पासवर्ड", type="password")
        if st.form_submit_button("प्रवेश करें"):
            if username_input == USERNAME and password_input == PASSWORD:
                st.session_state['authenticated'] = True
                st.rerun() 
            else:
                st.error("❌ गलत विवरण।")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    login_form()
    st.stop()
    
st.title("👨‍💼 Cloud Firestore कर्मचारी प्रबंधन प्रणाली")

@st.cache_data(ttl=300)
def load_employee_data():
    return get_all_employees()

employee_df = load_employee_data()

if st.sidebar.button("🚪 लॉग आउट"):
    st.session_state['authenticated'] = False
    st.rerun()

ALL_COLUMNS = [
    'S. No.', 'PF Number', EMPLOYEE_ID_KEY, 'Seniority No.', 'Unit', 'Employee Name', 'FATHER\'S NAME', 
    'Designation', 'STATION', 'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'Employee Name in Hindi', 
    'SF-11 short name', 'Gender ', 'Category', 'Designation in Hindi', 'Posting status', 
    'APPOINTMENT TYPE', 'PRMOTION DATE', 'DOR', 'Medical category', 'LAST PME', 'PME DUE', 
    'MEDICAL PLACE', 'LAST TRAINING', 'TRAINING DUE', 'SERVICE REMARK', 'EMPTYPE', 
    'PRAN', 'PENSIONACCNO', 'RAIL QUARTER NO.', 'CUG NUMBER', 'E-Number', 'UNIT No.', 
    'SICK FROM Date', 'PF No.', DOC_ID_KEY
]

# --- Tab Navigation ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 वर्तमान स्थिति", "➕ नया कर्मचारी जोड़ें", "✏️ अपडेट/हटाएँ", "📈 रिपोर्ट"])

# ===================================================================
# --- 1. वर्तमान स्थिति (READ) with Summary ---
# ===================================================================
with tab1:
    st.header("📋 कर्मचारी डैशबोर्ड और वर्तमान स्थिति")
    
    if not employee_df.empty:
        # --- 1. Summary Metrics ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("कुल कर्मचारी (Total)", len(employee_df))
        
        with col2:
            if 'Designation' in employee_df.columns:
                counts = employee_df['Designation'].value_counts()
                top_desig = counts.index[0] if not counts.empty else "N/A"
                st.metric("शीर्ष पद (Top Desig.)", f"{top_desig} ({counts.iloc[0]})")
        
        with col3:
            if 'PME DUE' in employee_df.columns:
                # Sirf unhe gine jinka PME due date bhara hua hai
                pme_filled = employee_df['PME DUE'].dropna().apply(lambda x: str(x).strip() != "").sum()
                st.metric("PME Records", pme_filled)

        st.markdown("---")
        
        # --- 2. PME Due Table ---
        st.subheader("⚠️ PME Due होने वाले कर्मचारी")
        if 'PME DUE' in employee_df.columns:
            # Filter rows jahan PME record hai
            pme_df = employee_df[employee_df['PME DUE'].notna() & (employee_df['PME DUE'] != "")].copy()
            if not pme_df.empty:
                st.dataframe(pme_df[['Employee Name', 'Designation', 'STATION', 'PME DUE']], hide_index=True, use_container_width=True)
            else:
                st.info("PME Due की कोई जानकारी नहीं मिली।")
        
        st.markdown("---")

        # --- 3. All Employees Table ---
        st.subheader("📝 सभी कर्मचारियों की विस्तृत सूची")
        display_cols = [col for col in ALL_COLUMNS if col in employee_df.columns]
        st.dataframe(employee_df[display_cols], width='stretch', hide_index=True)
        
        csv_data = employee_df.to_csv(index=False, encoding='utf-8').encode('utf-8')
        st.download_button("डाउनलोड CSV", csv_data, "employees.csv", "text/csv")
    else:
        st.info("डेटाबेस खाली है।")

# ===================================================================
# --- 2. नया कर्मचारी जोड़ें (CREATE) ---
# ===================================================================
with tab2:
    st.header("नया कर्मचारी जोड़ें")
    # Dropdown Options
    df_temp = employee_df.copy()
    DESIG_OPTS = sorted(df_temp['Designation'].dropna().unique().tolist()) if 'Designation' in df_temp.columns else []
    UNIT_OPTS = sorted(df_temp['Unit'].dropna().unique().tolist()) if 'Unit' in df_temp.columns else []
    NEW_FLAG = "➕ नया दर्ज करें"

    with st.form("add_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("नाम")
            hrms = st.text_input("HRMS ID")
            desig_sel = st.selectbox("पद", [None, NEW_FLAG] + DESIG_OPTS)
            desig = st.text_input("नया पद दर्ज करें") if desig_sel == NEW_FLAG else desig_sel
        with c2:
            pf = st.text_input("PF Number")
            unit_sel = st.selectbox("यूनिट", [None, NEW_FLAG] + UNIT_OPTS)
            unit = st.text_input("नई यूनिट दर्ज करें") if unit_sel == NEW_FLAG else unit_sel
            pme_due = st.date_input("PME Due Date", value=None)

        if st.form_submit_button("✅ सुरक्षित करें"):
            if name and hrms:
                new_data = {
                    "Employee Name": name, "HRMS ID": hrms, "Designation": desig,
                    "PF Number": pf, "Unit": unit, "PME DUE": str(pme_due) if pme_due else None,
                    "created_at": firestore.SERVER_TIMESTAMP
                }
                if add_employee(new_data):
                    st.success("सफलतापूर्वक जोड़ा गया!"); st.cache_data.clear(); st.rerun()
            else:
                st.error("नाम और HRMS ID अनिवार्य हैं।")

# ===================================================================
# --- 3. अपडेट/हटाएँ (UPDATE/DELETE) ---
# ===================================================================
with tab3:
    if not employee_df.empty:
        emp_list = employee_df.apply(lambda r: f"{r['Employee Name']} ({r[EMPLOYEE_ID_KEY]})", axis=1).tolist()
        selected = st.selectbox("कर्मचारी चुनें", emp_list)
        sel_id = selected.split('(')[-1].strip(')')
        curr = employee_df[employee_df[EMPLOYEE_ID_KEY] == sel_id].iloc[0]

        with st.form("update_form"):
            u_name = st.text_input("नाम", value=curr.get('Employee Name', ''))
            u_pme = st.text_input("PME DUE", value=curr.get('PME DUE', ''))
            if st.form_submit_button("✏️ अपडेट करें"):
                if update_employee(curr[DOC_ID_KEY], {"Employee Name": u_name, "PME DUE": u_pme}):
                    st.success("अपडेट सफल!"); st.cache_data.clear(); st.rerun()
        
        if st.button("🗑️ रिकॉर्ड हटाएं"):
            if delete_employee(curr[DOC_ID_KEY]):
                st.success("हटाया गया!"); st.cache_data.clear(); st.rerun()
    else:
        st.info("कोई डेटा नहीं।")

# ===================================================================
# --- 4. रिपोर्ट (REPORT) ---
# ===================================================================
with tab4:
    st.header("विश्लेषण")
    if not employee_df.empty:
        st.subheader("पद के अनुसार संख्या (Designation Wise)")
        if 'Designation' in employee_df.columns:
            st.bar_chart(employee_df['Designation'].value_counts())
        
        st.subheader("यूनिट के अनुसार संख्या (Unit Wise)")
        if 'Unit' in employee_df.columns:
            st.write(employee_df['Unit'].value_counts())
    else:
        st.info("रिपोर्ट के लिए डेटा उपलब्ध नहीं है।")
