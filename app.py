import streamlit as st
import fitz  # PyMuPDF
from google import genai
import hashlib

# --- CONFIGURATION ---
st.set_page_config(page_title="Email Heatmap", page_icon="🔥")

# --- UI HEADER ---
st.title("📧 Email Heatmap & Actionizer")
st.markdown("Upload a PDF thread to detect **urgency** and get **draft responses**.")

# --- SIDEBAR (Settings) ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Gemini API Key", type="password")
    st.info("Your key is safe and not stored permanently.")

# --- THE BRAIN (With Memory!) ---
# This @ symbol tells Streamlit: "If the input text hasn't changed, don't run this function again!"
@st.cache_data(show_spinner=False)
def analyze_email_with_memory(email_text, _client_key):
    # We create a new client inside the function to keep it fresh
    client = genai.Client(api_key=_client_key)
    
    prompt = f"""
    Act as a senior email analyst. Analyze the provided email thread.
    
    STRICT HEATMAP LOGIC:
    - RED: Rude tone, 3+ unresponded follow-ups, Management escalation, High business impact.
    - YELLOW: General follow-up, Operational, Medium impact.
    - BLUE: FYI, Spam, Tests, Vendor Junk, Stale threads.

    EMAIL TEXT:
    {email_text}

    RETURN YOUR ANSWER IN THIS EXACT FORMAT:
    CATEGORY: [RED or YELLOW or BLUE]
    SUMMARY: [1 sentence summary]
    ACTION: [1 sentence action]
    DRAFT: [The full email draft response]
    """
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp', contents=prompt
    )


# --- HELPER: TO EXTRACT TEXT FROM PDF ---
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# --- MAIN APP LOGIC ---
uploaded_file = st.file_uploader("Drop your PDF here...", type="pdf")

if uploaded_file and api_key:
    if st.button("🔥 Run Heatmap Analysis"):
        
        with st.spinner("Reading PDF..."):
            # 1. Extract Text
            email_content = extract_text_from_pdf(uploaded_file)
            
        with st.spinner("Consulting the AI... (Or checking memory)"):
            try:
                # 2. Ask AI (Memory is active here!)
                result_text = analyze_email_with_memory(email_content, api_key)
                
                # 3. Simple Parser to find the Category
                # We look at the first few lines to find RED, YELLOW, or BLUE
                category = "BLUE" # Default
                if "CATEGORY: RED" in result_text:
                    category = "RED"
                elif "CATEGORY: YELLOW" in result_text:
                    category = "YELLOW"
                
                # 4. Display the Heatmap
                st.divider()
                if category == "RED":
                    st.error(f"### 🔥 BURNING ISSUE (RED)\n\nThis thread requires immediate attention.")
                elif category == "YELLOW":
                    st.warning(f"### ⚠️ MODERATE ISSUE (YELLOW)\n\nThis needs a check-in soon.")
                else:
                    st.info(f"### 🧊 COLD / FYI (BLUE)\n\nNo immediate action required.")

                # 5. Show the Details
                st.markdown("### 📋 Analysis")
                st.write(result_text)

            except Exception as e:
                st.error(f"Something went wrong: {e}")

elif uploaded_file and not api_key:
    st.warning("👈 Please paste your API Key in the sidebar to start.")
