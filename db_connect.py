# db_connect.py (Updated for Streamlit Cloud Deployment)

# ... (Imports)
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json # इसे रखें

# लोकल फ़ाइल का नाम (Cloud पर इसका उपयोग नहीं होगा, लेकिन इसे local testing के लिए रखें)
SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json'
EMPLOYEE_COLLECTION = "employees"

@st.cache_resource
def initialize_firebase():
    """Firebase SDK को इनिशियलाइज़ करता है।"""
    try:
        if not firebase_admin._apps:
            
            # --- Cloud या Local की जाँच करें ---
            if st.secrets.get("firebase_config"):
                # 1. Cloud (Secrets) पर चल रहा है: st.secrets से क्रेडेंशियल्स लोड करें
                st.info("✅ Firebase: Streamlit Secrets का उपयोग कर रहा है।")
                
                # st.secrets एक डिक्शनरी को वापस करता है, इसलिए हम इसे सीधे credentials.Certificate को पास कर सकते हैं
                cred = credentials.Certificate(st.secrets["firebase_config"])
            
            else:
                # 2. Local मशीन पर चल रहा है: JSON फ़ाइल का उपयोग करें
                st.info("✅ Firebase: लोकल JSON फ़ाइल का उपयोग कर रहा है।")
                
                # Local File System से लोड करें
                with open(SERVICE_ACCOUNT_FILE) as f:
                    service_account_info = json.load(f)
                
                cred = credentials.Certificate(service_account_info)
            # ----------------------------------
            
            firebase_admin.initialize_app(cred)
            
        return firestore.client()
        
    except Exception as e:
        st.error(f"❌ Firebase कनेक्शन विफल। त्रुटि: {e}")
        return None

db = initialize_firebase()
# ... (बाकी कोड)

def get_all_employees():
    """Firestore से सभी कर्मचारियों को फ़ेच करता है और Pandas DataFrame लौटाता है।"""
    if db:
        # डेटा फ़ेच करें
        docs = db.collection(EMPLOYEE_COLLECTION).stream()
        data = []
        for doc in docs:
            # Firestore दस्तावेज़ ID को भी 'id' कॉलम के रूप में शामिल करें
            record = doc.to_dict()
            record['id'] = doc.id 
            data.append(record)
            
        # DataFrame में बदलें, इसे UI में उपयोग किया जाएगा
        if data:
            return pd.DataFrame(data)
    return pd.DataFrame() 

# बाकी CRUD (add_employee, update_employee, delete_employee) लॉजिक आपके app.py में इस्तेमाल होगा।
def add_employee(data):
    if db:
        db.collection(EMPLOYEE_COLLECTION).add(data)

def update_employee(employee_id, new_data):
    if db:
        db.collection(EMPLOYEE_COLLECTION).document(employee_id).update(new_data)

def delete_employee(employee_id):
    if db:
        db.collection(EMPLOYEE_COLLECTION).document(employee_id).delete()