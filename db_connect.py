# db_connect.py (Alternative Fix)

# ... (Imports)
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import json 
# ... (अन्य फ़ंक्शन)

@st.cache_resource
def initialize_firebase():
    """Firebase SDK को इनिशियलाइज़ करता है।"""
    try:
        if not firebase_admin._apps:
            
            # --- Cloud या Local की जाँच करें ---
            if st.secrets.get("firebase_config"):
                st.info("✅ Firebase: Streamlit Secrets का उपयोग कर रहा है।")
                
                # 1. AttrDict को मानक Python dict में बदलें
                service_account_info_attrdict = st.secrets["firebase_config"]
                final_credentials = dict(service_account_info_attrdict)
                
                # 2. FIX: private_key को साफ़ करना
                # Streamlit Secrets में private_key एक लंबी स्ट्रिंग के रूप में आती है
                # जिसमें '-----BEGIN PRIVATE KEY-----\n' आदि शामिल हैं।
                # हम JSON serialization से बचते हैं और सिर्फ private_key को ठीक करते हैं।

                # .toml फ़ाइल में 'private_key' ट्रिपल कोट्स में होना चाहिए
                # यदि नहीं है, तो हमें मैन्युअल रूप से \n को बदलना पड़ सकता है:
                
                # यदि private_key एक string है जिसमें literal \n है, तो उसे ठीक करें।
                if isinstance(final_credentials.get('private_key'), str):
                     final_credentials['private_key'] = final_credentials['private_key'].replace('\\n', '\n')
                
                cred = credentials.Certificate(final_credentials)
            
            else:
                # 2. Local मशीन पर चल रहा है: JSON फ़ाइल का उपयोग करें
                st.info("✅ Firebase: लोकल JSON फ़ाइल का उपयोग कर रहा है।")
                
                with open(SERVICE_ACCOUNT_FILE) as f:
                    service_account_info = json.load(f)
                
                cred = credentials.Certificate(service_account_info)
            # ----------------------------------
            
            firebase_admin.initialize_app(cred)
            
        return firestore.client()
        
    except Exception as e:
        # यह सुनिश्चित करने के लिए कि हम अभी भी त्रुटि देख सकते हैं
        st.error(f"❌ Firebase कनेक्शन विफल। त्रुटि: {e}")
        return None

db = initialize_firebase()

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


