import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json
from datetime import datetime

# --- ग्लोबल कॉन्फ़िगरेशन ---
# सुनिश्चित करें कि ये वैरिएबल्स किसी भी फ़ंक्शन (def) के बाहर हैं
SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json' # केवल लोकल टेस्टिंग के लिए आवश्यक
EMPLOYEE_COLLECTION = "employees" 

@st.cache_resource
def initialize_firebase():
    """Firebase SDK को इनिशियलाइज़ करता है और Firestore क्लाइंट लौटाता है।
    यह क्लाउड पर st.secrets का उपयोग करता है, और लोकल पर JSON फ़ाइल का।
    """
    try:
        if not firebase_admin._apps:
            
            if st.secrets.get("firebase_config"):
                # --- 1. Cloud (Secrets) पर चल रहा है ---
                st.info("✅ Firebase: Streamlit Secrets का उपयोग कर रहा है।")
                
                # FIX 1: AttrDict को मानक Python dict में बदलें
                service_account_info_attrdict = st.secrets["firebase_config"]
                final_credentials = dict(service_account_info_attrdict)

                # FIX 2: private_key में \n को ठीक करना
                # यह सुनिश्चित करता है कि Firebase SDK बहु-पंक्ति कुंजी को ठीक से पार्स कर सके।
                if isinstance(final_credentials.get('private_key'), str):
                     # \n (escape sequence) को literal newline character में बदलता है
                     final_credentials['private_key'] = final_credentials['private_key'].replace('\\n', '\n')
                
                cred = credentials.Certificate(final_credentials)
            
            else:
                # --- 2. Local मशीन पर चल रहा है ---
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

# Firebase क्लाइंट को इनिशियलाइज़ करें
db = initialize_firebase()


# =================================================================
# --- CRUD फ़ंक्शन्स ---
# =================================================================

def get_all_employees():
    """Firestore से सभी कर्मचारी डेटा प्राप्त करता है और उसे DataFrame के रूप में लौटाता है।"""
    data = []
    
    if db is None:
        return pd.DataFrame() # कनेक्शन विफल होने पर खाली DataFrame लौटाएँ

    try:
        # EMPLOYEE_COLLECTION ग्लोबल वेरिएबल का उपयोग करें
        docs = db.collection(EMPLOYEE_COLLECTION).stream()
        
        for doc in docs:
            record = doc.to_dict()
            record['id'] = doc.id # Firestore Document ID को जोड़ें
            data.append(record)
            
        if data:
            df = pd.DataFrame(data)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"डेटा लाने में त्रुटि: {e}")
        return pd.DataFrame()

def add_employee(employee_data):
    """Firestore में एक नया कर्मचारी रिकॉर्ड जोड़ता है।"""
    if db:
        try:
            db.collection(EMPLOYEE_COLLECTION).add(employee_data)
        except Exception as e:
            st.error(f"नया रिकॉर्ड जोड़ने में त्रुटि: {e}")

def update_employee(firestore_doc_id, updated_data):
    """Firestore में मौजूदा कर्मचारी रिकॉर्ड को अपडेट करता है।"""
    if db:
        try:
            doc_ref = db.collection(EMPLOYEE_COLLECTION).document(firestore_doc_id)
            doc_ref.update(updated_data)
        except Exception as e:
            st.error(f"रिकॉर्ड अपडेट करने में त्रुटि: {e}")

def delete_employee(firestore_doc_id):
    """Firestore से कर्मचारी रिकॉर्ड हटाता है।"""
    if db:
        try:
            db.collection(EMPLOYEE_COLLECTION).document(firestore_doc_id).delete()
        except Exception as e:
            st.error(f"रिकॉर्ड हटाने में त्रुटि: {e}")

# =================================================================
