import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai # <--- CHANGED LIBRARY
import json
import pandas as pd
from datetime import datetime
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Email Heatmap", page_icon="🔥", layout="wide")

# --- API KEY ---
DEFAULT_API_KEY = "AIzaSyCeevMmHPXwScyRlztI4lrqxHq2fkCokk4"

# --- UI HEADER ---
st.title("📧 Email Heatmap & Actionizer")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key_input = st.text_input("Gemini API Key", type="password", value=DEFAULT_API_KEY)
    api_key = api_key_input if api_key_input else DEFAULT_API_KEY
    
    current_user = st.text_input("Your Name (for the log)", value="Analyst")
    
    if api_key:
        st.success("Key connected! ✅")

# --- FUNCTION: LOGGING TO CSV ---
def save_to_history(filename, user, result_data):
    new_record = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User": user,
        "Filename": filename,
        "Heatmap Level": result_data.get('category', 'Unknown'),
        "Action Plan": result_data.get('action', 'N/A'),
        "Draft Subject": result_data.get('draft_subject', 'N/A')
    }
    
    log_file = "history.csv"
    file_exists = os.path.isfile(log_file)
    
    try:
        df = pd.DataFrame([new_record])
        df.to_csv(log_file, mode='a', header=not file_exists, index=False)
        return True
    except Exception as e:
        st.error(f"Could not save log: {e}")
        return False

# --- FUNCTION: AI ANALYSIS (STABLE VERSION) ---
@st.cache_data(show_spinner=False)
def analyze_email_with_memory(email_text, _client_key):
    # 1. Configure the STABLE library
    genai.configure(api_key=_client_key)
    
    # 2. Initialize the Model
    # We use 'gemini-1.5-flash' which works reliably in this SDK
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Act as a senior email analyst. Analyze the provided email thread.
    
    STRICT HEATMAP LOGIC:
    - RED: Rude tone, 3+ unresponded follow-ups, Management escalation, High business impact.
    - YELLOW: General follow-up, Operational, Medium impact.
    - BLUE: FYI, Spam, Tests, Vendor Junk, Stale threads.

    EMAIL TEXT:
    {email_text}

    Return a JSON object with these exact keys:
    {{
        "category": "RED or YELLOW or BLUE",
        "reason": "Short explanation",
        "action": "Recommended action",
        "draft_subject": "Draft email subject",
        "draft_body": "The polite email response text"
    }}
    """
    
    # 3. Generate Content
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

# --- FUNCTION: READ PDF ---
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# --- MAIN APP TABS ---
tab1, tab2 = st.tabs(["🔥 Run Analysis", "📜 History Log"])

# === TAB 1: THE ANALYZER ===
with tab1:
    st.markdown("Upload a PDF thread to detect **urgency** and get **draft responses**.")
    uploaded_file = st.file_uploader("Drop your PDF here...", type="pdf")

    if uploaded_file and api_key:
        if st.button("🔥 Run Heatmap Analysis"):
            
            with st.spinner("Reading PDF..."):
                uploaded_file.seek(0)
                email_content = extract_text_from_pdf(uploaded_file)
                
            with st.spinner("Consulting AI Brain..."):
                try:
                    # 1. Get Analysis
                    raw_json = analyze_email_with_memory(email_content, api_key)
                    data = json.loads(raw_json)
                    
                    # 2. Log the result
                    save_to_history(uploaded_file.name, current_user, data)
                    st.toast("Analysis saved to History Log! 📝")
                    
                    # 3. Display Results
                    st.divider()
                    
                    # Color-coded Alert Box
                    cat = data.get('category', 'BLUE').upper()
                    if "RED" in cat:
                        st.error(f"### 🔥 BURNING (RED)\n**Reason:** {data.get('reason')}")
                    elif "YELLOW" in cat:
                        st.warning(f"### ⚠️ MODERATE (YELLOW)\n**Reason:** {data.get('reason')}")
                    else:
                        st.info(f"### 🧊 COLD (BLUE)\n**Reason:** {data.get('reason')}")

                    # Columns for layout
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.subheader("✅ Action Plan")
                        st.write(data.get('action'))
                        
                    with col2:
                        st.subheader("✍️ Draft Response")
                        email_draft = f"Subject: {data.get('draft_subject')}\n\n{data.get('draft_body')}"
                        st.text_area("Copy this reply:", value=email_draft, height=300)

                except Exception as e:
                    st.error(f"Something went wrong: {e}")

# === TAB 2: THE HISTORY LOG ===
with tab2:
    st.header("🗂️ Analysis History")
    
    if os.path.exists("history.csv"):
        df = pd.read_csv("history.csv")
        df = df.iloc[::-1] # Reverse order
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Log as CSV",
            data=csv,
            file_name='heatmap_history.csv',
            mime='text/csv',
        )
    else:
        st.info("No history found yet. Run an analysis in the first tab!")
