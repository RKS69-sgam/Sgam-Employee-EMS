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
            
            if st.secrets.get("firebase_config"):
                st.info("✅ Firebase: Streamlit Secrets का उपयोग कर रहा है।")
                
                # FIX: Secrets को पहले JSON स्ट्रिंग में बदलें, फिर \n को ठीक करें।
                # यह सुनिश्चित करता है कि private_key में न्यूलाइन कैरेक्टर सही ढंग से डाले गए हैं।
                service_account_info_dict = st.secrets["firebase_config"]

                # डिक्शनरी को JSON स्ट्रिंग में बदलें
                json_string = json.dumps(service_account_info_dict)

                # Firebase SDK के लिए \n कैरेक्टर को वापस न्यूलाइन कैरेक्टर में बदलें
                # यह एक ज्ञात समस्या का समाधान है जब Streamlit Secrets से डेटा आता है।
                json_string_fixed = json_string.replace('\\n', '\n')

                # फिक्स्ड स्ट्रिंग को वापस Python डिक्शनरी में लोड करें
                final_credentials = json.loads(json_string_fixed)

                # अब credentials.Certificate को फिक्स्ड डिक्शनरी दें
                cred = credentials.Certificate(final_credentials)
            
            else:
                # 2. Local मशीन पर चल रहा है: JSON फ़ाइल का उपयोग करें
                st.info("✅ Firebase: लोकल JSON फ़ाइल का उपयोग कर रहा है।")
                # ... (लोकल फ़ाइल लोडिंग कोड)
                
            firebase_admin.initialize_app(cred)
            
        return firestore.client()
        
    except Exception as e:
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
