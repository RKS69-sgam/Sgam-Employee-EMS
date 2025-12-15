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

# --- ग्लोबल कॉन्फ़िगरेशन ---
SERVICE_ACCOUNT_FILE = 'sgamoffice-firebase-adminsdk-fbsvc-253915b05b.json' 
EMPLOYEE_COLLECTION = "employees" 
firestore = firestore

@st.cache_resource
def initialize_firebase():
    """Firebase SDK को इनिशियलाइज़ करता है और Firestore क्लाइंट लौटाता है।"""
    try:
        if not firebase_admin._apps:
            
            if st.secrets.get("firebase_config"):
                # --- 1. Cloud (Secrets) पर चल रहा है ---
                service_account_info_attrdict = st.secrets["firebase_config"]
                final_credentials = dict(service_account_info_attrdict)
                if isinstance(final_credentials.get('private_key'), str):
                     final_credentials['private_key'] = final_credentials['private_key'].replace('\\n', '\n')
                
                cred = credentials.Certificate(final_credentials)
            
            else:
                # --- 2. Local मशीन पर चल रहा है ---
                with open(SERVICE_ACCOUNT_FILE) as f:
                    service_account_info = json.load(f)
                cred = credentials.Certificate(service_account_info)
            
            firebase_admin.initialize_app(cred)
            
        return firestore.client()
        
    except Exception as e:
        st.error(f"❌ Firebase कनेक्शन विफल। त्रुटि: {e}")
        return None

db = initialize_firebase()


# --- CRUD फ़ंक्शन्स ---

def get_all_employees():
    """Firestore से सभी कर्मचारी डेटा प्राप्त करता है और उसे DataFrame के रूप में लौटाता है।"""
    data = []
    if db is None: return pd.DataFrame()

    try:
        docs = db.collection(EMPLOYEE_COLLECTION).stream()
        for doc in docs:
            record = doc.to_dict()
            record['id'] = doc.id # Firestore Document ID को जोड़ें
            data.append(record)
            
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"डेटा लाने में त्रुटि: {e}")
        return pd.DataFrame()

# 🚨 UPDATED CORE FIX FUNCTION
def clean_data_for_firestore(data):
    """
    Firestore को भेजे जाने से पहले डेटा को साफ़ करता है।
    - खाली स्ट्रिंग (`""`) को None में बदलता है।
    - खाली कुंजी (Key) वाले तत्वों को हटाता है।
    """
    cleaned_data = {}
    for key, value in data.items():
        # 1. कुंजी (Key) को साफ़ करें: सुनिश्चित करें कि यह खाली नहीं है
        if not key or not key.strip():
            continue # खाली कुंजी वाले फ़ील्ड को छोड़ दें
            
        # 2. मान (Value) को साफ़ करें: खाली स्ट्रिंग को None में बदलें
        if isinstance(value, str):
            if value.strip() == "":
                cleaned_data[key] = None
            else:
                cleaned_data[key] = value.strip() # अतिरिक्त स्पेस हटाएँ
        # 3. यदि मान NaN (Pandas/NumPy से) है, तो उसे भी None में बदलें
        elif pd.isna(value): 
             cleaned_data[key] = None
        else:
            cleaned_data[key] = value
            
    return cleaned_data


def add_employee(employee_data):
    """Firestore में एक नया कर्मचारी रिकॉर्ड जोड़ता है।"""
    if db:
        try:
            # Clean data before adding
            cleaned_data = clean_data_for_firestore(employee_data)
            db.collection(EMPLOYEE_COLLECTION).add(cleaned_data)
            return True 
        except Exception as e:
            st.error(f"नया रिकॉर्ड जोड़ने में त्रुटि: {e}")
            return False 

def update_employee(firestore_doc_id, updated_data):
    """Firestore में मौजूदा कर्मचारी रिकॉर्ड को अपडेट करता है।
    WARNING: इस संस्करण में, खाली स्ट्रिंग (या None) को DELETE_FIELD में बदला जाता है।
    """
    if db:
        try:
            # Clean data (empty string को None में बदलेगा)
            cleaned_data = clean_data_for_firestore(updated_data)
            
            final_update_data = {}
            for key, value in cleaned_data.items():
                # 🚨 यदि मान None है, तो उसे DELETE_FIELD में बदल दें (केवल परीक्षण के लिए)
                if value is None:
                    final_update_data[key] = firestore.DELETE_FIELD
                else:
                    final_update_data[key] = value

            if not final_update_data:
                 st.warning("कोई अपडेट डेटा नहीं भेजा गया।")
                 return True

            doc_ref = db.collection(EMPLOYEE_COLLECTION).document(firestore_doc_id)
            doc_ref.update(final_update_data) # फाइनल, साफ़ डेटा भेजा गया
            return True 
        except Exception as e:
            print(f"Firestore Update Failed for {firestore_doc_id}: {e}")
            st.error(f"रिकॉर्ड अपडेट करने में त्रुटि: {e}")
            return False 
    return False

def delete_employee(firestore_doc_id):
    """Firestore से कर्मचारी रिकॉर्ड हटाता है।"""
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

# --- 1. पेज कॉन्फ़िगरेशन ---
st.set_page_config(layout="wide", page_title="कर्मचारी प्रबंधन प्रणाली (Firestore)")

# --- ग्लोबल कॉन्फ़िगरेशन ---
EMPLOYEE_ID_KEY = 'HRMS ID' 
DOC_ID_KEY = 'id' 

# --- 2. ऑथेंटिकेशन लॉजिक ---

def login_form():
    st.title("🔒 लॉगिन आवश्यक")

    if 'app_auth' not in st.secrets:
        st.error("❌ त्रुटि: 'app_auth' Secrets में परिभाषित नहीं है।")
        st.stop()
        
    USERNAME = st.secrets["app_auth"].get("username", "admin")
    PASSWORD = st.secrets["app_auth"].get("password", "Sgam@1234") 

    with st.form("login_form"):
        st.subheader("लॉग इन करें")
        username_input = st.text_input("यूजरनेम")
        password_input = st.text_input("पासवर्ड", type="password")
        login_button = st.form_submit_button("प्रवेश करें")

        if login_button:
            if username_input == USERNAME and password_input == PASSWORD:
                st.session_state['authenticated'] = True
                st.success("✅ सफलतापूर्वक लॉग इन किया गया।")
                st.rerun() 
            else:
                st.error("❌ गलत यूजरनेम या पासवर्ड।")

# --- 3. ऑथेंटिकेशन की जाँच करें ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    login_form()
    st.stop()
    
st.title("👨‍💼 Cloud Firestore कर्मचारी प्रबंधन प्रणाली")

if db is None:
    st.warning("कृपया डेटाबेस कनेक्शन समस्याओं को ठीक करें।")
    st.stop()
    
# डेटा कैशिंग फ़ंक्शन
@st.cache_data(ttl=300)
def load_employee_data():
    return get_all_employees()

employee_df = load_employee_data()

# --- लॉग आउट बटन ---
if st.sidebar.button("🚪 लॉग आउट"):
    st.session_state['authenticated'] = False
    st.rerun()

# ALL_COLUMNS सूची में सभी सटीक नाम
ALL_COLUMNS = [
    'S. No.', 'PF Number', EMPLOYEE_ID_KEY, 'Seniority No.', 'Unit', 'Employee Name', 'FATHER\'S NAME', 
    'Designation', 'STATION', 'PAY LEVEL', 'BASIC PAY', 'DOB', 'DOA', 'Employee Name in Hindi', 
    'SF-11 short name', 'Gender', 'Category', 'Designation in Hindi', 'Posting status', 
    'APPOINTMENT TYPE', 'PRMOTION DATE', 'DOR', 'Medical category', 'LAST PME', 'PME DUE', 
    'MEDICAL PLACE', 'LAST TRAINING', 'TRAINING DUE', 'SERVICE REMARK', 'EMPTYPE', 
    'PRAN', 'PENSIONACCNO', 'RAIL QUARTER NO.', 'CUG NUMBER', 'E-Number', 'UNIT No.', 
    'SICK FROM Date', 'PF No.', 
    DOC_ID_KEY
]

# --- टैब नेविगेशन ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 वर्तमान स्थिति", "➕ नया कर्मचारी जोड़ें", "✏️ अपडेट/हटाएँ", "📈 रिपोर्ट"])

# ===================================================================
# --- 1. वर्तमान स्थिति (READ) ---
# ===================================================================
with tab1:
    st.header("वर्तमान कर्मचारी सूची (सभी फ़ील्ड सहित)")
    
    if not employee_df.empty:
        display_cols = [col for col in ALL_COLUMNS if col in employee_df.columns]
        st.dataframe(employee_df[display_cols], use_container_width=True, hide_index=True)
        st.markdown(f"**कुल कर्मचारी:** {len(employee_df)}")
        
        csv_data = employee_df.to_csv(index=False, encoding='utf-8').encode('utf-8')
        st.download_button(
            label="डेटा CSV के रूप में डाउनलोड करें (सभी फ़ील्ड)",
            data=csv_data,
            file_name='employee_full_report_tab1.csv',
            mime='text/csv',
            key='download_tab1' 
        )
    else:
        st.info("कोई कर्मचारी रिकॉर्ड नहीं मिला।")

# ===================================================================
# --- 2. नया कर्मचारी जोड़ें (CREATE) ---
# ===================================================================
with tab2:
    st.header("नया कर्मचारी जोड़ें (सभी फ़ील्ड)")
    with st.form("add_employee_form"):
        st.subheader("I. व्यक्तिगत और पद विवरण")
        col_c1, col_c2, col_c3 = st.columns(3)
        
        with col_c1:
            name = st.text_input("कर्मचारी का नाम (Employee Name)", key="add_name")
            father_name = st.text_input("पिता का नाम (FATHER\'S NAME)", key="add_fname")
            designation = st.text_input("पद/Designation", key="add_designation")
            hrms_id = st.text_input(f"{EMPLOYEE_ID_KEY} (Unique)", key="add_hrms_id")
        
        with col_c2:
            pf_number = st.text_input("PF नंबर (PF Number)", key="add_pf_number")
            dob = st.date_input("जन्म तिथि (DOB)", key="add_dob", value=None)
            doa = st.date_input("नियुक्ति तिथि (DOA)", key="add_doa", value=None)
            dor = st.date_input("सेवानिवृत्ति (DOR)", key="add_dor", value=None)
            
        with col_c3:
            station = st.text_input("स्टेशन (STATION)", key="add_station")
            unit = st.text_input("यूनिट (Unit)", key="add_unit")
            pay_level = st.text_input("पे लेवल (PAY LEVEL)", key="add_pay_level") 
            basic_pay = st.number_input("मूल वेतन (BASIC PAY)", key="add_basic_pay", value=0, step=100)
            
        st.markdown("---")
        st.subheader("II. अन्य विवरण")
        col_c4, col_c5, col_c6 = st.columns(3)
        
        with col_c4:
            cug_number = st.text_input("CUG नंबर (CUG NUMBER)", key="add_cug")
            rail_quarter_no = st.text_input("रेल क्वार्टर नं. (RAIL QUARTER NO.)", key="add_quarter")
            medical_category = st.text_input("चिकित्सा श्रेणी (Medical category)", key="add_med_cat")
            employee_name_in_hindi = st.text_input("नाम हिंदी में (Employee Name in Hindi)", key="add_name_hi")
            designation_in_hindi = st.text_input("पद हिंदी में (Designation in Hindi)", key="add_des_hi")

        with col_c5:
            last_pme = st.date_input("पिछला PME (LAST PME)", key="add_last_pme", value=None)
            pme_due = st.date_input("अगला PME देय (PME DUE)", key="add_pme_due", value=None)
            last_training = st.date_input("पिछली ट्रेनिंग (LAST TRAINING)", key="add_last_training", value=None)

        with col_c6:
            pran = st.text_input("PRAN", key="add_pran")
            pensionaccno = st.text_input("पेंशन खाता संख्या (PENSIONACCNO)", key="add_pensionaccno")
            gender = st.selectbox("लिंग (Gender)", ["Male", "Female", "Other", None], key="add_gender")

        submitted = st.form_submit_button("✅ नया कर्मचारी जोड़ें")
        
        if submitted:
            if name and hrms_id:
                if hrms_id in employee_df[EMPLOYEE_ID_KEY].values: 
                    st.error(f"यह {EMPLOYEE_ID_KEY} ({hrms_id}) पहले से मौजूद है।")
                    st.stop()
                    
                new_employee_data = {
                    "Employee Name": name,
                    EMPLOYEE_ID_KEY: hrms_id, 
                    "FATHER'S NAME": father_name,
                    "Designation": designation,
                    "STATION": station,
                    "PF Number": pf_number,
                    "Unit": unit,
                    "PAY LEVEL": pay_level,
                    "BASIC PAY": basic_pay,
                    "DOB": str(dob) if dob else None,
                    "DOA": str(doa) if doa else None,
                    "DOR": str(dor) if dor else None,
                    "CUG NUMBER": cug_number,
                    "RAIL QUARTER NO.": rail_quarter_no,
                    "Medical category": medical_category,
                    "LAST PME": str(last_pme) if last_pme else None,
                    "PME DUE": str(pme_due) if pme_due else None,
                    "LAST TRAINING": str(last_training) if last_training else None,
                    "PRAN": pran,
                    "PENSIONACCNO": pensionaccno,
                    "Gender": gender,
                    "Employee Name in Hindi": employee_name_in_hindi,
                    "Designation in Hindi": designation_in_hindi,
                    "created_at": firestore.SERVER_TIMESTAMP
                }
                
                if add_employee(new_employee_data):
                    st.success("कर्मचारी सफलतापूर्वक जोड़ा गया।")
                    st.cache_data.clear() 
                    st.rerun() 
                else:
                    st.error("कर्मचारी जोड़ने में विफलता। कृपया लॉग्स की जाँच करें।")
            else:
                st.error("नाम और HRMS ID अनिवार्य हैं।")

# ===================================================================
# --- 3. अपडेट/हटाएँ (UPDATE/DELETE) ---
# ===================================================================
with tab3:
    st.header("कर्मचारी विवरण अपडेट/हटाएँ (सभी फ़ील्ड)")
    
    if not employee_df.empty:
        selection = st.selectbox(
            "अपडेट करने के लिए कर्मचारी चुनें", 
            employee_df.apply(lambda row: f"{row.get('Employee Name', 'N/A')} ({row.get(EMPLOYEE_ID_KEY, 'N/A')})", axis=1).tolist()
        )
        
        selected_hrms_id = selection.split('(')[-1].strip(')')
        
        current_data = employee_df[employee_df[EMPLOYEE_ID_KEY] == selected_hrms_id].iloc[0]
        selected_firestore_id = current_data[DOC_ID_KEY] 
        
        st.subheader(f"ID: {selected_hrms_id} का विवरण संपादित करें") 

        key_prefix = f"update_{selected_hrms_id}_" 
        
        # --- UPDATE FORM ---
        with st.form("update_employee_form"):
            
            st.subheader("I. मुख्य विवरण")
            col_u1, col_u2, col_u3 = st.columns(3)
            with col_u1:
                new_name = st.text_input("नाम (Employee Name)", value=current_data.get('Employee Name', ''), key=key_prefix + 'upd_name')
                new_designation = st.text_input("पद (Designation)", value=current_data.get('Designation', ''), key=key_prefix + 'upd_designation')
                new_father_name = st.text_input("पिता का नाम (FATHER\'S NAME)", value=current_data.get('FATHER\'S NAME', ''), key=key_prefix + 'upd_fname')
                new_name_hindi = st.text_input("नाम हिंदी में (Employee Name in Hindi)", value=current_data.get('Employee Name in Hindi', ''), key=key_prefix + 'upd_name_hi')
                
            with col_u2:
                new_station = st.text_input("स्टेशन (STATION)", value=current_data.get('STATION', ''), key=key_prefix + 'upd_station')
                new_pf_number = st.text_input("PF नंबर (PF Number)", value=current_data.get('PF Number', ''), key=key_prefix + 'upd_pf_number')
                new_unit = st.text_input("यूनिट (Unit)", value=current_data.get('Unit', ''), key=key_prefix + 'upd_unit')
                new_designation_hindi = st.text_input("पद हिंदी में (Designation in Hindi)", value=current_data.get('Designation in Hindi', ''), key=key_prefix + 'upd_des_hi')
                
            with col_u3:
                new_dob = st.text_input("जन्म तिथि (DOB)", value=current_data.get('DOB', ''), key=key_prefix + 'upd_dob')
                new_doa = st.text_input("नियुक्ति तिथि (DOA)", value=current_data.get('DOA', ''), key=key_prefix + 'upd_doa')
                new_dor = st.text_input("सेवानिवृत्ति (DOR)", value=current_data.get('DOR', ''), key=key_prefix + 'upd_dor')
                new_pay_level = st.text_input("पे लेवल (PAY LEVEL)", value=current_data.get('PAY LEVEL', ''), key=key_prefix + 'upd_pay_level')
                new_basic_pay = st.text_input("मूल वेतन (BASIC PAY)", value=current_data.get('BASIC PAY', ''), key=key_prefix + 'upd_basic_pay')

            st.markdown("---")
            st.subheader("II. संपर्क और अन्य विवरण")
            col_u4, col_u5, col_u6 = st.columns(3)
            with col_u4:
                new_quarter = st.text_input("रेल क्वार्टर नं. (RAIL QUARTER NO.)", value=current_data.get('RAIL QUARTER NO.', ''), key=key_prefix + 'upd_quarter')
                new_cug = st.text_input("CUG नंबर (CUG NUMBER)", value=current_data.get('CUG NUMBER', ''), key=key_prefix + 'upd_cug')
                new_pran = st.text_input("PRAN", value=current_data.get('PRAN', ''), key=key_prefix + 'upd_pran')

            with col_u5:
                new_med_cat = st.text_input("चिकित्सा श्रेणी (Medical category)", value=current_data.get('Medical category', ''), key=key_prefix + 'upd_med_cat')
                new_last_pme = st.text_input("पिछला PME (LAST PME)", value=current_data.get('LAST PME', ''), key=key_prefix + 'upd_last_pme')
                new_pme_due = st.text_input("अगला PME देय (PME DUE)", value=current_data.get('PME DUE', ''), key=key_prefix + 'upd_pme_due')
            
            with col_u6:
                new_last_training = st.text_input("पिछली ट्रेनिंग (LAST TRAINING)", value=current_data.get('LAST TRAINING', ''), key=key_prefix + 'upd_last_training')
                new_gender = st.text_input("लिंग (Gender)", value=current_data.get('Gender', ''), key=key_prefix + 'upd_gender')
                new_pensionaccno = st.text_input("पेंशन खाता संख्या (PENSIONACCNO)", value=current_data.get('PENSIONACCNO', ''), key=key_prefix + 'upd_pensionaccno')
                
            update_button = st.form_submit_button("✏️ विवरण अपडेट करें")

            if update_button:
                if not new_name or not selected_hrms_id:
                    st.error("नाम और HRMS ID अनिवार्य हैं।")
                else:
                    # FIX: Empty Element त्रुटि को हल करने के लिए BASIC PAY को संख्या में बदलें
                    try:
                        # सुनिश्चित करें कि BASIC PAY एक संख्या (या स्ट्रिंग) है
                        # यदि यह पूरी तरह से डिजिट है, तो int में बदलें, अन्यथा स्ट्रिंग ही रहने दें
                        basic_pay_val = int(new_basic_pay) if new_basic_pay and str(new_basic_pay).isdigit() else new_basic_pay
                    except Exception:
                        st.error("मूल वेतन (BASIC PAY) में अमान्य संख्या दर्ज की गई है। कृपया ठीक करें।")
                        st.stop()
                        
                    updated_data = {
                        "Employee Name": new_name,
                        "Designation": new_designation,
                        "FATHER'S NAME": new_father_name,
                        "STATION": new_station,
                        "PF Number": new_pf_number,
                        "Unit": new_unit,
                        "DOB": new_dob, 
                        "DOA": new_doa,
                        "DOR": new_dor,
                        "RAIL QUARTER NO.": new_quarter,
                        "CUG NUMBER": new_cug,
                        "PRAN": new_pran,
                        "Medical category": new_med_cat,
                        "LAST PME": new_last_pme,
                        "PME DUE": new_pme_due,
                        "PAY LEVEL": new_pay_level,
                        "BASIC PAY": basic_pay_val, 
                        "Employee Name in Hindi": new_name_hindi,
                        "Designation in Hindi": new_designation_hindi,
                        "LAST TRAINING": new_last_training,
                        "Gender": new_gender,
                        "PENSIONACCNO": new_pensionaccno
                    }
                    
                    with st.spinner(f'कर्मचारी {selected_hrms_id} को अपडेट किया जा रहा है...'):
                        success = update_employee(selected_firestore_id, updated_data)
                    
                    if success:
                        st.success(f"कर्मचारी **{new_name} ({selected_hrms_id})** सफलतापूर्वक अपडेट किया गया।")
                        st.cache_data.clear()
                        st.rerun() 
                    else:
                        st.error("अपडेट विफल रहा। कृपया Streamlit Logs की जाँच करें कि Firestore क्या त्रुटि दे रहा है।")
        
        # --- DELETE BUTTON (फॉर्म के बाहर) ---
        st.markdown("---")
        
        delete_key = key_prefix + "delete_record_btn"
        
        if st.button("🗑️ इस रिकॉर्ड को हटाएँ", help="यह डेटाबेस से कर्मचारी को स्थायी रूप से हटा देगा।", key=delete_key):
            if st.session_state.get(f'confirm_delete_{selected_hrms_id}', False):
                if delete_employee(selected_firestore_id):
                    st.success(f"रिकॉर्ड {selected_hrms_id} सफलतापूर्वक हटाया गया।")
                    st.session_state[f'confirm_delete_{selected_hrms_id}'] = False
                    st.cache_data.clear() 
                    st.rerun()
                else:
                    st.error("हटाने में विफलता।")
            else:
                st.session_state[f'confirm_delete_{selected_hrms_id}'] = True
                st.warning("हटाने की पुष्टि के लिए फिर से 'इस रिकॉर्ड को हटाएँ' दबाएँ।")
    else:
        st.info("कोई कर्मचारी रिकॉर्ड नहीं मिला।")


# ===================================================================
# --- 4. रिपोर्ट और विश्लेषण (FINAL & STABLE) ---
# ===================================================================
with tab4:
    st.header("कर्मचारी रिपोर्ट और विश्लेषण")
    
    if not employee_df.empty:
        # 1. कुल कर्मचारी
        total_employees = len(employee_df)
        st.metric(label="📊 कुल कर्मचारी (Total Employees)", value=total_employees)
        
        st.markdown("---")
        
        col_r1, col_r2 = st.columns(2)
        
        # 2. पद (Designation) के अनुसार सारांश
        with col_r1:
            st.subheader("👨‍💻 पद के अनुसार वितरण (Designation Wise)")
            if 'Designation' in employee_df.columns:
                designation_counts = employee_df['Designation'].value_counts(dropna=True)
                st.bar_chart(designation_counts)
                st.dataframe(designation_counts.rename("Count"), use_container_width=True)
            else:
                st.info("डेटाबेस में 'Designation' कॉलम नहीं मिला।")

        # 3. यूनिट (Unit) के अनुसार सारांश
        with col_r2:
            st.subheader("🏢 यूनिट के अनुसार वितरण (Unit Wise)")
            # यह आपके द्वारा बताए गए सभी यूनिटों (30, 31, T/M, W/S, आदि) को कवर करेगा।
            if 'Unit' in employee_df.columns:
                unit_counts = employee_df['Unit'].value_counts(dropna=True)
                st.bar_chart(unit_counts)
                st.dataframe(unit_counts.rename("Count"), use_container_width=True)
            else:
                st.info("डेटाबेस में 'Unit' कॉलम नहीं मिला।")

        st.markdown("---")
        
        col_r3, col_r4 = st.columns(2)
        
        # 4. लिंग (Gender) के अनुसार सारांश
        with col_r3:
            st.subheader("🚻 लिंग के अनुसार वितरण (Gender Wise)")
            if 'Gender' in employee_df.columns:
                gender_counts = employee_df['Gender'].value_counts(dropna=True)
                st.bar_chart(gender_counts)
                st.dataframe(gender_counts.rename("Count"), use_container_width=True)
            else:
                st.info("डेटाबेस में 'Gender' कॉलम नहीं मिला।")
            
        # 5. श्रेणी (Category) के अनुसार सारांश
        with col_r4:
            st.subheader("🏷️ श्रेणी के अनुसार वितरण (Category Wise)")
            if 'Category' in employee_df.columns:
                category_counts = employee_df['Category'].value_counts(dropna=True)
                st.bar_chart(category_counts)
                st.dataframe(category_counts.rename("Count"), use_container_width=True)
            else:
                st.info("डेटाबेस में 'Category' कॉलम नहीं मिला।")

        st.markdown("---")
        
        # CSV डाउनलोड बटन
        csv = employee_df.to_csv(index=False, encoding='utf-8').encode('utf-8')
        st.download_button(
            label="डेटा CSV के रूप में डाउनलोड करें (सभी फ़ील्ड)",
            data=csv,
            file_name='employee_full_report.csv',
            mime='text/csv',
            key='download_tab4'
        )
    else:
        st.info("कोई कर्मचारी रिकॉर्ड नहीं मिला।")




