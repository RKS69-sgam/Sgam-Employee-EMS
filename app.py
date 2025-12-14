# app.py (Updated with Login Security)

import streamlit as st
import pandas as pd
from datetime import datetime
from db_connect import db, get_all_employees, add_employee, update_employee, delete_employee, firestore # db_connect से आयात

# --- 1. पेज कॉन्फ़िगरेशन ---
st.set_page_config(layout="wide", page_title="कर्मचारी प्रबंधन प्रणाली (Firestore)")

# --- 2. ऑथेंटिकेशन लॉजिक ---

def login_form():
    """यूजरनेम/पासवर्ड इनपुट दिखाता है और लॉगिन स्थिति प्रबंधित करता है।"""
    st.title("🔒 लॉगिन आवश्यक")

    # Secrets से क्रेडेंशियल्स लोड करें
    if 'app_auth' not in st.secrets:
        st.error("❌ त्रुटि: 'app_auth' Secrets में परिभाषित नहीं है।")
        st.stop()
    
    USERNAME = st.secrets["app_auth"].get("username", "admin")
    PASSWORD = st.secrets["app_auth"].get("password", "Sgam@1234") # आपके द्वारा प्रदान किया गया डिफ़ॉल्ट

    with st.form("login_form"):
        st.subheader("लॉग इन करें")
        username_input = st.text_input("यूजरनेम")
        password_input = st.text_input("पासवर्ड", type="password")
        login_button = st.form_submit_button("प्रवेश करें")

        if login_button:
            # पासवर्ड की जाँच करें
            if username_input == USERNAME and password_input == PASSWORD:
                st.session_state['authenticated'] = True
                st.success("✅ सफलतापूर्वक लॉग इन किया गया।")
                st.rerun() # मुख्य ऐप लोड करने के लिए रीलोड करें
            else:
                st.error("❌ गलत यूजरनेम या पासवर्ड।")

# --- 3. ऑथेंटिकेशन की जाँच करें ---

# यदि सत्र अवस्था (session state) में 'authenticated' नहीं है, तो उसे False सेट करें
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# यदि लॉग इन नहीं है, तो लॉगिन फॉर्म दिखाएँ और मुख्य ऐप को रोक दें
if not st.session_state['authenticated']:
    login_form()
    st.stop()
    
# यदि लॉग इन है, तो मुख्य ऐप चलाएँ
st.title("👨‍💼 Cloud Firestore कर्मचारी प्रबंधन प्रणाली")

# Firestore कनेक्शन की जाँच करें
if db is None:
    st.warning("कृपया डेटाबेस कनेक्शन समस्याओं को ठीक करें।")
    st.stop()
    
# डेटा कैशिंग फ़ंक्शन
@st.cache_data(ttl=300)
def load_employee_data():
    # यह सुनिश्चित करें कि यह फ़ंक्शन db_connect.py से सही डेटा ला रहा है
    return get_all_employees()

employee_df = load_employee_data()

# --- लॉग आउट बटन ---
if st.sidebar.button("🚪 लॉग आउट"):
    st.session_state['authenticated'] = False
    st.rerun()

# --- मुख्य ऐप UI (पिछले कोड का बाकी हिस्सा यहाँ शुरू होता है) ---

# CSV से लिए गए सभी 36 कॉलम (साफ़ नाम)
ALL_COLUMNS = [
    's_no', 'pf_number', 'hrms_id', 'seniority_no', 'unit', 'employee_name', 'father_s_name', 
    'designation', 'station', 'pay_level', 'basic_pay', 'dob', 'doa', 'employee_name_in_hindi', 
    'sf_11_short_name', 'gender', 'category', 'designation_in_hindi', 'posting_status', 
    'appointment_type', 'prmotion_date', 'dor', 'medical_category', 'last_pme', 'pme_due', 
    'medical_place', 'last_training', 'training_due', 'service_remark', 'emptype', 
    'pran', 'pensionaccno', 'rail_quarter_no', 'cug_number', 'e_number', 'unit_no'
]

# --- टैब नेविगेशन ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 वर्तमान स्थिति", "➕ नया कर्मचारी जोड़ें", "✏️ अपडेट/हटाएँ", "📈 रिपोर्ट"])

# ===================================================================
# --- 1. वर्तमान स्थिति (READ) ---
# ===================================================================
with tab1:
    st.header("वर्तमान कर्मचारी सूची (सभी फ़ील्ड सहित)")
    
    if not employee_df.empty:
        # प्रदर्शित करने के लिए अनावश्यक कॉलम हटाएँ
        display_cols = [col for col in ALL_COLUMNS if col in employee_df.columns]
        st.dataframe(employee_df[display_cols], use_container_width=True, hide_index=True)
        st.markdown(f"**कुल कर्मचारी:** {len(employee_df)}")
    else:
        st.info("कोई कर्मचारी रिकॉर्ड नहीं मिला।")

# ===================================================================
# --- 2. नया कर्मचारी जोड़ें (CREATE) ---
# ... (टैब 2, 3, और 4 का कोड वही रहता है जैसा आपने पिछले चरण में ठीक किया था।)

# ... (बाकी टैब 2, 3, और 4 का कोड यहाँ जारी रखें)

# ===================================================================
# --- 2. नया कर्मचारी जोड़ें (CREATE) ---
# ===================================================================
with tab2:
    st.header("नया कर्मचारी जोड़ें (सभी फ़ील्ड)")
    with st.form("add_employee_form"):
        st.subheader("I. व्यक्तिगत और पद विवरण")
        col_c1, col_c2, col_c3 = st.columns(3)
        
        # Row 1
        with col_c1:
            name = st.text_input("कर्मचारी का नाम", key="add_name")
            father_name = st.text_input("पिता का नाम", key="add_fname")
            designation = st.text_input("पद/Designation", key="add_designation")
            hrms_id = st.text_input("HRMS ID (Unique)", key="add_hrms_id")
        
        with col_c2:
            pf_number = st.text_input("PF नंबर", key="add_pf_number")
            dob = st.date_input("जन्म तिथि (DOB)", key="add_dob", value=None)
            doa = st.date_input("नियुक्ति तिथि (DOA)", key="add_doa", value=None)
            dor = st.date_input("सेवानिवृत्ति (DOR)", key="add_dor", value=None)
            
        with col_c3:
            station = st.text_input("स्टेशन", key="add_station")
            unit = st.text_input("यूनिट", key="add_unit")
            pay_level = st.text_input("पे लेवल", key="add_pay_level")
            basic_pay = st.number_input("मूल वेतन (Basic Pay)", key="add_basic_pay", value=None, step=100)
            
        st.markdown("---")
        st.subheader("II. अन्य विवरण")
        col_c4, col_c5, col_c6 = st.columns(3)
        
        with col_c4:
            cug_number = st.text_input("CUG नंबर", key="add_cug")
            rail_quarter_no = st.text_input("रेल क्वार्टर नं.", key="add_quarter")
            medical_category = st.text_input("चिकित्सा श्रेणी", key="add_med_cat")

        with col_c5:
            last_pme = st.date_input("पिछला PME", key="add_last_pme", value=None)
            pme_due = st.date_input("अगला PME देय", key="add_pme_due", value=None)
            last_training = st.date_input("पिछली ट्रेनिंग", key="add_last_training", value=None)

        with col_c6:
            pran = st.text_input("PRAN", key="add_pran")
            pensionaccno = st.text_input("पेंशन खाता संख्या", key="add_pensionaccno")
            gender = st.selectbox("लिंग (Gender)", ["Male", "Female", "Other", None], key="add_gender")

        submitted = st.form_submit_button("✅ नया कर्मचारी जोड़ें")
        
        if submitted:
            if name and hrms_id:
                # सभी फ़ील्ड के लिए डेटा डिक्शनरी तैयार करें
                new_employee_data = {
                    "employee_name": name,
                    "hrms_id": hrms_id,
                    "father_s_name": father_name,
                    "designation": designation,
                    "station": station,
                    "pf_number": pf_number,
                    "unit": unit,
                    "pay_level": pay_level,
                    "basic_pay": basic_pay,
                    "dob": str(dob) if dob else None,
                    "doa": str(doa) if doa else None,
                    "dor": str(dor) if dor else None,
                    "cug_number": cug_number,
                    "rail_quarter_no": rail_quarter_no,
                    "medical_category": medical_category,
                    "last_pme": str(last_pme) if last_pme else None,
                    "pme_due": str(pme_due) if pme_due else None,
                    "last_training": str(last_training) if last_training else None,
                    "pran": pran,
                    "pensionaccno": pensionaccno,
                    "gender": gender,
                    "created_at": firestore.SERVER_TIMESTAMP
                }
                add_employee(new_employee_data)
                st.success("कर्मचारी सफलतापूर्वक जोड़ा गया।")
                st.cache_data.clear() 
                st.rerun() 
            else:
                st.error("नाम और HRMS ID अनिवार्य हैं।")

# ===================================================================
# --- 3. अपडेट/हटाएँ (UPDATE/DELETE) ---
# ===================================================================
with tab3:
    st.header("कर्मचारी विवरण अपडेट/हटाएँ (सभी फ़ील्ड)")
    
    if not employee_df.empty:
        # कर्मचारी को HRMS ID या नाम से चुनें
        selection = st.selectbox(
            "अपडेट करने के लिए कर्मचारी चुनें", 
            employee_df.apply(lambda row: f"{row.get('employee_name', 'N/A')} ({row.get('hrms_id', 'N/A')})", axis=1).tolist()
        )
        
        selected_hrms_id = selection.split('(')[-1].strip(')')
        current_data = employee_df[employee_df['hrms_id'] == selected_hrms_id].iloc[0]
        selected_firestore_id = current_data['id'] 
        
        st.subheader(f"ID: {selected_hrms_id} का विवरण संपादित करें")

        # FIX: Dynamic Key Prefix बनाना जो चयनित कर्मचारी ID पर निर्भर करता है
        key_prefix = f"update_{selected_hrms_id}_" 
        
        # --- UPDATE FORM ---
        with st.form("update_employee_form"):
            
            st.subheader("I. मुख्य विवरण")
            col_u1, col_u2, col_u3 = st.columns(3)
            with col_u1:
                # Dynamic Key का उपयोग करें: key=key_prefix + 'upd_name'
                new_name = st.text_input("नाम", value=current_data.get('employee_name', ''), key=key_prefix + 'upd_name')
                new_designation = st.text_input("पद", value=current_data.get('designation', ''), key=key_prefix + 'upd_designation')
                new_father_name = st.text_input("पिता का नाम", value=current_data.get('father_s_name', ''), key=key_prefix + 'upd_fname')
            with col_u2:
                new_station = st.text_input("स्टेशन", value=current_data.get('station', ''), key=key_prefix + 'upd_station')
                new_pf_number = st.text_input("PF नंबर", value=current_data.get('pf_number', ''), key=key_prefix + 'upd_pf_number')
                new_unit = st.text_input("यूनिट", value=current_data.get('unit', ''), key=key_prefix + 'upd_unit')
            with col_u3:
                new_dob = st.text_input("जन्म तिथि (DOB)", value=current_data.get('dob', ''), key=key_prefix + 'upd_dob')
                new_doa = st.text_input("नियुक्ति तिथि (DOA)", value=current_data.get('doa', ''), key=key_prefix + 'upd_doa')
                new_dor = st.text_input("सेवानिवृत्ति (DOR)", value=current_data.get('dor', ''), key=key_prefix + 'upd_dor')

            st.markdown("---")
            st.subheader("II. संपर्क और अन्य विवरण")
            col_u4, col_u5, col_u6 = st.columns(3)
            with col_u4:
                new_quarter = st.text_input("रेल क्वार्टर नं.", value=current_data.get('rail_quarter_no', ''), key=key_prefix + 'upd_quarter')
                new_cug = st.text_input("CUG नंबर", value=current_data.get('cug_number', ''), key=key_prefix + 'upd_cug')
                new_pran = st.text_input("PRAN", value=current_data.get('pran', ''), key=key_prefix + 'upd_pran')

            with col_u5:
                new_med_cat = st.text_input("चिकित्सा श्रेणी", value=current_data.get('medical_category', ''), key=key_prefix + 'upd_med_cat')
                new_last_pme = st.text_input("पिछला PME", value=current_data.get('last_pme', ''), key=key_prefix + 'upd_last_pme')
                new_pme_due = st.text_input("अगला PME देय", value=current_data.get('pme_due', ''), key=key_prefix + 'upd_pme_due')
            
            with col_u6:
                new_pay_level = st.text_input("पे लेवल", value=current_data.get('pay_level', ''), key=key_prefix + 'upd_pay_level')
                new_basic_pay = st.text_input("मूल वेतन", value=current_data.get('basic_pay', ''), key=key_prefix + 'upd_basic_pay')
                
            update_button = st.form_submit_button("✏️ विवरण अपडेट करें")

            if update_button:
                # केवल उन फ़ील्ड को अपडेट करें जो फॉर्म में बदले गए हैं
                updated_data = {
                    "employee_name": new_name,
                    "designation": new_designation,
                    "father_s_name": new_father_name,
                    "station": new_station,
                    "pf_number": new_pf_number,
                    "unit": new_unit,
                    "dob": new_dob,
                    "doa": new_doa,
                    "dor": new_dor,
                    "rail_quarter_no": new_quarter,
                    "cug_number": new_cug,
                    "pran": new_pran,
                    "medical_category": new_med_cat,
                    "last_pme": new_last_pme,
                    "pme_due": new_pme_due,
                    "pay_level": new_pay_level,
                    "basic_pay": new_basic_pay
                }
                update_employee(selected_firestore_id, updated_data)
                st.success(f"कर्मचारी {new_name} ({selected_hrms_id}) सफलतापूर्वक अपडेट किया गया।")
                st.cache_data.clear()
                st.rerun()

        # --- DELETE BUTTON (फॉर्म के बाहर) ---
        st.markdown("---")
        
        # FIX: Delete बटन की Key को भी Dynamic बनाया गया है
        if st.button("🗑️ इस रिकॉर्ड को हटाएँ", help="यह डेटाबेस से कर्मचारी को स्थायी रूप से हटा देगा।", key=key_prefix + "delete_record_btn"):
            if st.warning(f"क्या आप वाकई {current_data.get('employee_name')} ({selected_hrms_id}) को हटाना चाहते हैं?"):
                if st.button("हाँ, पुष्टि करें और हटाएँ", key=key_prefix + "confirm_delete_btn"):
                    delete_employee(selected_firestore_id)
                    st.success(f"रिकॉर्ड {selected_hrms_id} सफलतापूर्वक हटाया गया।")
                    st.cache_data.clear()
                    st.rerun()

# ===================================================================
# --- 4. रिपोर्ट और विश्लेषण ---
# ===================================================================
with tab4:
    st.header("कर्मचारी रिपोर्ट और विश्लेषण")
    
    if not employee_df.empty:
        # पद के आधार पर कर्मचारियों की संख्या
        st.subheader("पद के अनुसार वितरण")
        designation_counts = employee_df['designation'].value_counts().head(10)
        st.bar_chart(designation_counts)
        
        # यूनिट के अनुसार वितरण
        st.subheader("यूनिट के अनुसार वितरण")
        unit_counts = employee_df['unit'].value_counts().head(10)
        st.bar_chart(unit_counts)
        
        # डेटा को CSV के रूप में डाउनलोड करें
        csv = employee_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="डेटा CSV के रूप में डाउनलोड करें (सभी फ़ील्ड)",
            data=csv,
            file_name='employee_full_report.csv',
            mime='text/csv',
        )

# --- अंत: मुख्य ऐप UI ---