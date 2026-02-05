import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
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
    
    # --- DIAGNOSTIC TOOL: LIST MODELS ---
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.success("System Connected! ✅")
            
            # Show available models in an expander so we can debug if needed
            with st.expander("Show Available Models"):
                try:
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    st.write(models)
                except:
                    st.write("Could not list models.")
        except Exception as e:
            st.error(f"Connection failed: {e}")

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

# --- FUNCTION: AI ANALYSIS (SELF-HEALING) ---
@st.cache_data(show_spinner=False)
def analyze_email_with_memory(email_text, _client_key):
    genai.configure(api_key=_client_key)
    
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
    
    # --- SMART MODEL SELECTOR ---
    # We try 3 models in order. If one fails, we catch the error and try the next.
    model_options = [
        'gemini-1.5-flash',       # First choice (Fastest)
        'gemini-1.5-flash-001',   # Second choice (Pinned version)
        'gemini-1.5-flash-002',   # Third choice (Newest)
        'gemini-pro'              # Fallback (Old reliable)
    ]
    
    last_error = None
    
    for model_name in model_options:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return response.text # If successful, return immediately
        except Exception as e:
            last_error = e
            continue # Try the next model in the list
            
    # If we run out of models, raise the last error
    raise last_error

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
                    
                    cat = data.get('category', 'BLUE').upper()
                    if "RED" in cat:
                        st.error(f"### 🔥 BURNING (RED)\n**Reason:** {data.get('reason')}")
                    elif "YELLOW" in cat:
                        st.warning(f"### ⚠️ MODERATE (YELLOW)\n**Reason:** {data.get('reason')}")
                    else:
                        st.info(f"### 🧊 COLD (BLUE)\n**Reason:** {data.get('reason')}")

                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.subheader("✅ Action Plan")
                        st.write(data.get('action'))
                        
                    with col2:
                        st.subheader("✍️ Draft Response")
                        email_draft = f"Subject: {data.get('draft_subject')}\n\n{data.get('draft_body')}"
                        st.text_area("Copy this reply:", value=email_draft, height=300)

                except Exception as e:
                    st.error(f"All models failed. Last error: {e}")

# === TAB 2: THE HISTORY LOG ===
with tab2:
    st.header("🗂️ Analysis History")
    if os.path.exists("history.csv"):
        df = pd.read_csv("history.csv")
        df = df.iloc[::-1]
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download CSV", data=csv, file_name='heatmap_history.csv', mime='text/csv')
    else:
        st.info("No history found yet.")
