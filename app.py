import streamlit as st
import os
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# Import your existing backend
# NOTE: Ensure agent.py is in the same folder and has the 'graph' object
from agent import graph 

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="CSE Smart Scout", page_icon="🇱🇰")

st.title("CSE Smart Scout")
st.caption("AI Financial Analyst for the Colombo Stock Exchange")

# --- SIDEBAR (API KEYS) ---
with st.sidebar:
    st.header("Configuration")
    
    # Check if keys exist in environment (.env), otherwise ask user
    load_dotenv()
    
    if not os.getenv("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = st.text_input("Groq API Key", type="password")
        
    if not os.getenv("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = st.text_input("Tavily API Key", type="password")
        
    st.markdown("---")
    st.markdown("**Capabilities:**")
    st.markdown("- 📈 Real-time CSE Prices")
    st.markdown("- 📰 Market News Analysis")
    st.markdown("- 🧠 Comparative Reasoning")

# --- CHAT HISTORY ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [AIMessage(content="Hello! I can track CSE stock prices and analyze market news. Ask me about JKH, COMB, or generic market trends.")]

# --- DISPLAY CHAT ---
for msg in st.session_state["messages"]:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, AIMessage):
        # We only show the final text, not the tool calls, to keep it clean
        if msg.content:
            st.chat_message("assistant").write(msg.content)

# --- USER INPUT ---
user_query = st.chat_input("Ask about a stock (e.g., 'Compare JKH and DIAL')")

if user_query:
    # 1. Display User Message
    st.chat_message("user").write(user_query)
    st.session_state["messages"].append(HumanMessage(content=user_query))
    
    # 2. Run the Agent (with Visual Thinking)
    with st.chat_message("assistant"):
        container = st.empty()
        thought_process = st.expander("🧠 View Agent Logic (Reasoning & Tools)", expanded=True)
        
        # We need to track the 'accumulator' to show the streaming process
        full_response = ""
        
        # Run the LangGraph
        try:
            # We use 'stream' to get events one by one
            events = graph.stream(
                {"messages": st.session_state["messages"]},
                stream_mode="values"
            )
            
            for event in events:
                msg = event["messages"][-1]
                
                # A. Tool Execution (The "Thinking")
                if isinstance(msg, ToolMessage):
                    thought_process.write(f"🔌 **Tool Output:** `{str(msg.content)[:100]}...`")
                
                # B. Agent Planning (The "Intent")
                elif isinstance(msg, AIMessage) and msg.tool_calls:
                    for t in msg.tool_calls:
                        thought_process.write(f"🛠️ **Plan:** Calling `{t['name']}` with `{t['args']}`")
                
                # C. Final Answer
                elif isinstance(msg, AIMessage) and msg.content:
                    full_response = msg.content
                    container.markdown(full_response)
            
            # 3. Save Context
            if full_response:
                st.session_state["messages"].append(AIMessage(content=full_response))
                
        except Exception as e:
            st.error(f"An error occurred: {e}")