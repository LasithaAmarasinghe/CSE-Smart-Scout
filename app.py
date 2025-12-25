import streamlit as st
import os
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# Import your backend graph
# NOTE: Ensure agent.py is in the same directory
from agent import graph 

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="CSE Smart Scout", 
    page_icon="🇱🇰", 
    layout="wide"
)

st.title("CSE Smart Scout 🤖")
st.caption("Agentic Financial Analyst for the Colombo Stock Exchange (Powered by LangGraph)")

# --- 2. SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("Configuration")
    load_dotenv()
    
    # Secure API Key Entry
    if not os.getenv("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = st.text_input("Groq API Key", type="password")
    
    if not os.getenv("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = st.text_input("Tavily API Key", type="password")

    st.divider()
    st.markdown("### 🛠️ System Status")
    st.info("Architecture: **Multi-Agent Hierarchical**")
    st.markdown("- **Supervisor:** Routes tasks")
    st.markdown("- **Analyst:** Quant (Prices, RSI)")
    st.markdown("- **Researcher:** Qualitative (News)")
    
    if st.button("Clear Chat History"):
        st.session_state["messages"] = [
            AIMessage(content="Hello! I am your CSE market assistant. Ask me about **JKH**, **Dialog**, or current market trends.")
        ]
        st.rerun()

# --- 3. CHAT HISTORY ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        AIMessage(content="Hello! I am your CSE market assistant. Ask me about **JKH**, **Dialog**, or current market trends.")
    ]

# Display existing chat messages
for msg in st.session_state["messages"]:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        # We only show the final text, not the tool calls, to keep the main chat clean
        st.chat_message("assistant").write(msg.content)

# --- 4. MAIN LOGIC (USER INPUT) ---
user_query = st.chat_input("Ask about a stock (e.g., 'Analyze JKH technicals')")

if user_query:
    # A. Display User Message
    st.chat_message("user").write(user_query)
    st.session_state["messages"].append(HumanMessage(content=user_query))
    
    # B. Run the Agent
    with st.chat_message("assistant"):
        response_container = st.empty()
        
        # We use an expander to show the "Thought Process" without cluttering the UI
        # This solves the "messy UI" problem you had
        with st.expander("🧠 Agent Reasoning (Live Logs)", expanded=False):
            status_placeholder = st.empty()
            
            # TRACKER: Keeps track of how many messages we've already processed
            # This solves the "Duplicate Output" problem
            last_msg_count = len(st.session_state["messages"])
            
            try:
                # Run the graph with a higher recursion limit (Solves the "Recursion limit" error)
                events = graph.stream(
                    {"messages": st.session_state["messages"]},
                    stream_mode="values",
                    config={"recursion_limit": 50} 
                )
                
                for event in events:
                    current_messages = event["messages"]
                    
                    # IGNORE steps that didn't add a new message (e.g., pure routing steps)
                    if len(current_messages) <= last_msg_count:
                        continue
                        
                    # Get the NEW message
                    msg = current_messages[-1]
                    last_msg_count = len(current_messages) # Update tracker

                    # --- RENDER LOGIC based on Message Type ---
                    
                    # 1. Tool Execution (The "Thinking")
                    if isinstance(msg, ToolMessage):
                        status_placeholder.markdown(f"🔌 **Tool Output:** Received data from `{msg.name}`.")
                        # Display JSON nicely instead of raw text
                        st.json(msg.content[:500] + "..." if len(msg.content) > 500 else msg.content)
                    
                    # 2. Agent Planning (The "Intent")
                    elif isinstance(msg, AIMessage) and msg.tool_calls:
                        for t in msg.tool_calls:
                            status_placeholder.markdown(f"🛠️ **Agent Action:** Calling `{t['name']}`...")
                            st.write(f"Arguments: `{t['args']}`")
                    
                    # 3. Final Answer
                    elif isinstance(msg, AIMessage) and msg.content:
                        # Clear the status text so the final answer stands out
                        status_placeholder.empty()
                        response_container.markdown(msg.content)
            
            except Exception as e:
                st.error(f"Agent Logic Error: {e}")
                st.info("Tip: Try clearing the conversation history.")

        # C. Save Final Response to History
        # We check the event stream's final state to ensure consistency
        if 'current_messages' in locals() and current_messages:
            final_msg = current_messages[-1]
            if isinstance(final_msg, AIMessage) and final_msg.content:
                # Only append if it's not already the last message (double safety)
                if st.session_state["messages"][-1] != final_msg:
                    st.session_state["messages"].append(final_msg)