import streamlit as st
import json
from groq import Groq
from github import Github
import time
import re

# --- 1. CORE SYNC ---
@st.cache_resource
def init_nexus():
    try:
        g_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        gh = Github(st.secrets["GH_TOKEN"])
        r = gh.get_repo(st.secrets["GH_REPO"])
        return g_client, r
    except Exception as e:
        st.error(f"Sync Offline: {e}")
        return None, None

client, repo = init_nexus()

# --- 2. THEME & STYLING (unchanged) ---
st.set_page_config(page_title="Nexus Omni", layout="wide", initial_sidebar_state="collapsed")

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark"

if st.session_state.theme_mode == "Dark":
    bg, card, text, accent = "#0E1117", "#1A1C23", "#E0E0E0", "#58a6ff"
else:
    bg, card, text, accent = "#F0F2F6", "#FFFFFF", "#1E1E1E", "#007BFF"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="st-"] {{ font-family: 'Inter', sans-serif; background-color: {bg} !important; color: {text} !important; }}
    div[data-testid="stVerticalBlock"] > div:has(div.stMarkdown) {{
        background: {card}; border-radius: 16px; padding: 24px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
    }}
    .main-title {{ font-size: 36px; font-weight: 600;
        background: linear-gradient(120deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    [data-testid="stSidebar"] {{ display: none; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. HEADER ---
c_head1, c_head2, c_head3, c_head4 = st.columns([5, 2, 2, 2])
with c_head1:
    st.markdown('<div class="main-title">Nexus Omni <span style="font-size:14px; color:gray;">v2.4 Agent</span></div>', unsafe_allow_html=True)
with c_head2:
    st.session_state.theme_mode = st.selectbox("Appearance", ["Dark", "Light"], label_visibility="collapsed")
with c_head3:
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
with c_head4:
    selected_model = st.selectbox("Model", ["llama-3.3-70b-versatile", "llama3-8b-8192 (faster)"], label_visibility="collapsed")

# --- 4. TOOLS (unchanged) ---
def get_tools():
    return [ ... ]  # Keep exact same as v2.3

def execute_tool(tool_call, repo):
    # Keep exact same as v2.3

# --- 5. CONTROL CENTER (unchanged vault/delete fixes) ---
col_writer, col_chat = st.columns([4, 6], gap="large")
# ... (keep your writer and vault code from v2.3)

with col_chat:
    st.subheader("💬 Nexus Intelligent Agent")
    chat_box = st.container(height=580, border=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with chat_box.chat_message(m["role"]):
            st.markdown(m["content"])

    # Suggestions (updated for memory)
    s1, s2, s3, s4 = st.columns(4)
    p_cmd = None
    if s1.button("🔍 Audit Code"): p_cmd = "Audit all Python files and fix issues."
    if s2.button("📐 UI UX"): p_cmd = "Suggest advanced UI upgrades."
    if s3.button("🧠 Sync Memory"): p_cmd = "Read memory_general.json, update with current goals/progress (main: world's most powerful AI app with vision/code exec/self-improve)."
    if s4.button("🚀 Build Tool"): p_cmd = "Build a useful new script."

    query = st.chat_input("Command the Nexus...") or p_cmd

# --- 6. AGENT WITH RATE LIMIT HANDLING ---
if query and client and repo:
    st.session_state.messages.append({"role": "user", "content": query})
    with chat_box.chat_message("user"): st.markdown(query)
    
    with chat_box.chat_message("assistant"):
        with st.spinner("Thinking..."):
            messages = [
                {"role": "system", "content": """You are Nexus Omni v2.4 - autonomous agent.
Use tools precisely. Keep responses concise to save tokens.
Always update memory_general.json with progress/goals."""}
            ]
            messages.extend(st.session_state.messages[-10:])  # Reduced for token savings
            
            final_response = ""
            tool_feedback = ""
            max_loops = 5
            for _ in range(max_loops):
                try:
                    comp = client.chat.completions.create(
                        model=selected_model,
                        messages=messages,
                        tools=get_tools(),
                        tool_choice="auto",
                        max_tokens=2048,  # Reduced
                        temperature=0.6
                    )
                    choice = comp.choices[0].message
                    
                    if choice.content:
                        final_response += choice.content + "\n\n"
                    
                    if not getattr(choice, "tool_calls", None):
                        break
                    
                    tool_feedback = ""
                    for tool_call in choice.tool_calls:
                        result = execute_tool(tool_call, repo)
                        result_obj = json.loads(result) if result.startswith("{") else {"raw": result}
                        status = result_obj.get("status", "done")
                        tool_feedback += f"**{tool_call.function.name}** → {status}\n"
                        
                        messages.append(choice)
                        messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": result})
                
                except Exception as e:
                    error_str = str(e)
                    if "rate_limit" in error_str or "429" in error_str:
                        # Extract retry time if available
                        match = re.search(r"try again in ([\d.m]+s)", error_str)
                        retry = match.group(1) if match else "1 hour"
                        final_response += f"🚫 Groq rate limit hit (free tier). Retry in ~{retry}.\nUpgrade your API key limits at console.groq.com."
                        break
                    else:
                        final_response += f"❌ Error: {error_str}"
                        break
            
            full_output = (tool_feedback + final_response).strip() or "Task complete."
            st.markdown(full_output)
            st.session_state.messages.append({"role": "assistant", "content": full_output})
            st.rerun()
