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
# --- 1. SAFE DATA CLEANER ---
# =================================================================
def clean_payload_final(raw_data):
    """Khaali aur 'Unnamed' columns ko database se bahar rakhta hai"""
    clean_data = {}
    for key, val in raw_data.items():
        key_str = str(key).strip()
        # Sirf unhi keys ko rakhein jo valid hain aur Excel ka kachra nahi hain
        if key_str and not key_str.startswith('Unnamed'):
            v_str = str(val).strip() if val is not None else ""
            clean_data[key_str] = v_str if v_str != "" else None
    return clean_data

# =================================================================
# --- 2. AUTHENTICATION (admin / Sgam@4321) ---
# =================================================================
st.set_page_config(layout="wide", page_title="Railway Management")

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
                st.error("❌ Invalid Login")
    st.stop()

# =================================================================
# --- 3. MAIN APPLICATION ---
# =================================================================
def get_data():
    docs = db.collection(EMPLOYEE_COLLECTION).stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        data.append(d)
    return pd.DataFrame(data)

employee_df = get_data()

# Headers based on your uploaded Excel
ALL_COLS = [
    'S. No.', 'Employee Name', 'Employee Name in Hindi', 'HRMS ID', 'PF Number', 
    'FATHER\'S NAME', 'Designation', 'Designation in Hindi', 'Unit', 'STATION', 
    'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'DOR', 'Seniority No.', 'Category', 
    'Medical category', 'PME DUE', 'LAST PME', 'TRAINING DUE', 'LAST TRAINING', 
    'PRMOTION DATE', 'PRAN', 'Gender ', 'CUG NUMBER', 'RAIL QUARTER NO.', 
    'Posting status', 'APPOINTMENT TYPE', 'EMPTYPE', 'PENSIONACCNO', 'E-Number', 
    'UNIT No.', 'SICK FROM Date', 'SERVICE REMARK', 'MEDICAL PLACE', 'SF-11 short name'
]

tab1, tab2, tab3 = st.tabs(["📊 डैशबोर्ड", "➕ नया कर्मचारी", "✏️ अपडेट/हटाएँ"])

with tab1:
    st.header("📋 मास्टर लिस्ट")
    if not employee_df.empty:
        csv = employee_df.drop(columns=['id'], errors='ignore').to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 डेटाबेस CSV डाउनलोड करें", csv, "Railway_Backup.csv", "text/csv")
        st.dataframe(employee_df.drop(columns=['id'], errors='ignore'), use_container_width=True)

with tab3:
    st.header("✏️ रिकॉर्ड अपडेट या डिलीट करें")
    if not employee_df.empty:
        names = employee_df.apply(lambda r: f"{r.get('Employee Name')} ({r.get('HRMS ID')})", axis=1).tolist()
        sel_name = st.selectbox("कर्मचारी चुनें", names)
        h_id = sel_name.split('(')[-1].strip(')')
        rec = employee_df[employee_df['HRMS ID'] == h_id].iloc[0]

        # UPDATE FORM
        with st.form("update_employee_form"):
            st.warning(f"एडिट हो रहा है: {sel_name}")
            new_vals = {}
            cols = st.columns(3)
            for i, col in enumerate(ALL_COLS):
                with cols[i % 3]:
                    old_val = rec.get(col, "")
                    new_vals[col] = st.text_input(col, value=str(old_val) if old_val is not None else "")
            
            submit = st.form_submit_button("💾 बदलाव सुरक्षित करें (Update)")
            
            if submit:
                final_up = clean_payload_final(new_vals)
                if final_up:
                    db.collection(EMPLOYEE_COLLECTION).document(rec['id']).update(final_up)
                    st.success("डेटा अपडेट हो गया!")
                    st.rerun()

        # DELETE SECTION (Separate from Form for safety)
        st.write("---")
        st.subheader("⚠️ खतरनाक जोन (Danger Zone)")
        st.write(f"क्या आप वाकई **{sel_name}** का रिकॉर्ड डिलीट करना चाहते हैं?")
        
        # Confirmation check for delete
        col_del1, col_del2 = st.columns([1, 4])
        with col_del1:
            if st.button("🗑️ रिकॉर्ड डिलीट करें", type="secondary", help="यह रिकॉर्ड हमेशा के लिए हटा देगा"):
                db.collection(EMPLOYEE_COLLECTION).document(rec['id']).delete()
                st.error(f"रिकॉर्ड {sel_name} डिलीट कर दिया गया है।")
                st.rerun()
