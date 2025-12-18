import os
import json
from typing import Annotated, Literal
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_groq import ChatGroq
from langchain_core.messages import ToolMessage, SystemMessage, AIMessage

# --- IMPORT YOUR TOOLS ---
from cse_tools import get_cse_stock_price, search_market_news, get_market_overview

# --- 1. SETUP ---
# Ensure API Key is present
load_dotenv()
api_key = os.getenv("GROQ_API_KEY") 

class State(TypedDict):
    messages: Annotated[list, add_messages]

# --- 2. THE BRAIN ---
# Using Llama-3-70b for best reasoning
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

SYSTEM_INSTRUCTIONS = """You are a Senior Financial Analyst for the Colombo Stock Exchange (CSE).

CORE RULES:
1. **Context is King:** Only answer questions about Sri Lankan stocks.
2. **Anti-Hallucination:** If the Search Tool returns news about "Cricket" (e.g., Pramodaya Wickramasinghe), "Pakistan" (e.g., PICIC, Crescent Star), or unrelated companies, YOU MUST IGNORE IT.
3. **Honesty:** If the news is irrelevant, explicitly say: "No relevant financial news found."
4. **Formatting:** Always show the price clearly in LKR.
"""

# Bind the tools so the LLM knows they exist
tools = [get_cse_stock_price, search_market_news, get_market_overview]
llm_with_tools = llm.bind_tools(tools)

# --- 3. NODES ---

def chatbot_node(state: State):
    """Decides what to do next."""
    print("--- DEBUG: Brain is Thinking... ---")
    
    # 1. Get the current conversation history
    messages = state["messages"]
    
    # 2. Prepend the System Instructions
    # We create a temporary list so we don't mess up the actual chat history in the UI
    messages_with_rules = [SystemMessage(content=SYSTEM_INSTRUCTIONS)] + messages
    
    # 3. Invoke the LLM with the Rules + History
    return {"messages": [llm_with_tools.invoke(messages_with_rules)]}

def tool_node(state: State):
    """Executes the tools."""
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_outputs = []
    
    # Iterate through all tool calls the LLM requested
    for tool_call in last_message.tool_calls:
        print(f"--- DEBUG: Executing Tool '{tool_call['name']}' ---")
        
        try:
            if tool_call["name"] == "get_cse_stock_price":
                result = get_cse_stock_price(tool_call["args"]["ticker"])
            elif tool_call["name"] == "search_market_news":
                # Handle cases where 'query' argument might be missing or named differently
                q = tool_call["args"].get("query", "Sri Lanka Market News")
                result = search_market_news(q)
            elif tool_call["name"] == "get_market_overview":
                result = get_market_overview()
            else:
                result = f"Error: Tool '{tool_call['name']}' not found."
                
        except Exception as e:
            result = f"Error executing tool: {str(e)}"

        # Verify we actually got data
        print(f"--- DEBUG: Tool returned: {str(result)[:50]}... ---")

        tool_outputs.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"]
            )
        )
            
    return {"messages": tool_outputs}

# --- 4. LOGIC ---

def should_continue(state: State) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

# --- 5. GRAPH BUILD ---
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot_node)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", should_continue)
graph_builder.add_edge("tools", "chatbot")

graph = graph_builder.compile()

# --- 6. RUNNER ---
if __name__ == "__main__":
    print("\n🚀 DIAGNOSTIC AGENT STARTED. Type 'quit' to exit.")
    
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ["quit", "exit"]:
            break
            
        print("\n--- Starting Cycle ---")
        try:
            events = graph.stream(
                {"messages": [("user", user_input)]},
                stream_mode="values"
            )
            
            for event in events:
                msg = event["messages"][-1]
                
                # PRINT EVERYTHING (No filtering)
                if isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        print(f"🧠 PLAN: Call {msg.tool_calls[0]['name']}")
                    else:
                        print(f"🤖 AGENT: {msg.content}")
                elif isinstance(msg, ToolMessage):
                    print(f"🔌 TOOL RESULT: Data received.")
                    
        except Exception as e:
            print(f"🔥 CRITICAL ERROR IN LOOP: {e}")