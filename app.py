import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# =================================================================
# --- 0. FIREBASE SETUP ---
# =================================================================
SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json' 
EMPLOYEE_COLLECTION = "employees" 

@st.cache_resource
def initialize_firebase():
    if not firebase_admin._apps:
        try:
            if st.secrets.get("firebase_config"):
                cred = credentials.Certificate(dict(st.secrets["firebase_config"]))
            else:
                cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Firebase Init Error: {e}")
    return firestore.client()

db = initialize_firebase()

# =================================================================
# --- 1. THE FIX: CLEANING FUNCTION ---
# =================================================================
def get_clean_payload(raw_data):
    """
    ValueError: Empty element ko fix karne ke liye function.
    Yeh khali keys aur 'Unnamed' columns ko nikal deta hai.
    """
    clean_dict = {}
    for k, v in raw_data.items():
        key_str = str(k).strip()
        # 1. Check ki key khali na ho
        # 2. Check ki key 'Unnamed' se shuru na ho
        if key_str and not key_str.startswith("Unnamed"):
            # Value ko string mein badlein aur khali hone par None (Null) karein
            val_str = str(v).strip() if v is not None else ""
            clean_dict[key_str] = val_str if val_str != "" else None
    return clean_dict

# =================================================================
# --- 2. UI & UPDATE LOGIC ---
# =================================================================
st.title("🚀 Railway Employee Management")

# Data Fetching
def get_data():
    docs = db.collection(EMPLOYEE_COLLECTION).stream()
    data = [ {**doc.to_dict(), 'id': doc.id} for doc in docs ]
    return pd.DataFrame(data)

df = get_data()

# Aapki file ke headers (Exact list)
ALL_COLS = [
    'S. No.', 'Employee Name', 'Employee Name in Hindi', 'HRMS ID', 'PF Number', 
    'FATHER\'S NAME', 'Designation', 'Unit', 'STATION', 'PAY LEVEL', 'BASIC PAY', 
    'DOB', 'DOA', 'DOR', 'Seniority No.', 'Category', 'Medical category', 
    'PME DUE', 'LAST PME', 'TRAINING DUE', 'LAST TRAINING', 'PRMOTION DATE', 
    'PRAN', 'Gender ', 'CUG NUMBER', 'RAIL QUARTER NO.', 'Posting status', 
    'APPOINTMENT TYPE', 'EMPTYPE', 'E-Number'
]

if not df.empty:
    st.subheader("✏️ रिकॉर्ड अपडेट करें")
    search_list = df.apply(lambda r: f"{r.get('Employee Name')} ({r.get('HRMS ID')})", axis=1).tolist()
    selected_emp = st.selectbox("कर्मचारी चुनें", search_list)
    
    # Selected record nikaalein
    h_id = selected_emp.split('(')[-1].strip(')')
    record = df[df['HRMS ID'] == h_id].iloc[0]

    with st.form("update_form"):
        updated_values = {}
        cols = st.columns(3)
        
        for i, col_name in enumerate(ALL_COLS):
            with cols[i % 3]:
                # Old value dikhayein
                current_val = record.get(col_name, "")
                updated_values[col_name] = st.text_input(col_name, value=str(current_val))

        if st.form_submit_button("💾 सुरक्षित करें"):
            # ERROR PREVENTER: Payload clean karein
            final_payload = get_clean_payload(updated_values)
            
            if final_payload:
                try:
                    db.collection(EMPLOYEE_COLLECTION).document(record['id']).update(final_payload)
                    st.success("डेटा अपडेट हो गया!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Firestore Error: {e}")
            else:
                st.warning("अपडेट करने के लिए कोई मान्य डेटा नहीं मिला।")
