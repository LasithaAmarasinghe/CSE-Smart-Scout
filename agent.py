import os
import operator
from typing import Annotated, Sequence, TypedDict, Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

# --- IMPORT TOOLS ---
from cse_tools import get_cse_stock_price, web_search, get_technical_indicators

load_dotenv()

# --- 1. MODEL CONFIGURATION ---
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# --- 2. AGENT STATE ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    sender: str

# --- 3. HELPER ---
def create_agent(llm, tools, system_message: str):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="messages"),
    ])
    if tools:
        return prompt | llm.bind_tools(tools)
    return prompt | llm

# --- 4. AGENTS (ANTI-LOOP PROMPTS) ---

# -- Technical Analyst --
analyst_agent = create_agent(
    llm,
    [get_cse_stock_price, get_technical_indicators],
    "You are a Technical Analyst. "
    "RULES:"
    "1. Fetch data using tools."
    "2. IF you already see the tool output in the chat history, DO NOT call the tool again."
    "3. SUMMARIZE the data immediately in plain English."
    "4. Your job is DONE after the summary."
)

# -- Market Researcher --
researcher_agent = create_agent(
    llm,
    [web_search],
    "You are a Market Researcher. "
    "1. Search for news using 'web_search'."
    "2. Summarize the headlines."
    "3. Do not ask follow-up questions. Just report."
)

# --- 5. NODES ---

def analyst_node(state):
    result = analyst_agent.invoke(state)
    if isinstance(result, AIMessage):
        result.name = "Technical_Analyst"
    return {"messages": [result], "sender": "Technical_Analyst"}

def researcher_node(state):
    result = researcher_agent.invoke(state)
    if isinstance(result, AIMessage):
        result.name = "Market_Researcher"
    return {"messages": [result], "sender": "Market_Researcher"}

# --- 6. SUPERVISOR (STRICT FINISH LOGIC) ---

class RouteResponse(BaseModel):
    next: Literal["Technical_Analyst", "Market_Researcher", "FINISH"]

def supervisor_node(state):
    messages = state["messages"]
    
    # AGGRESSIVE PROMPT TO STOP LOOPS
    system_prompt = (
        "You are a Supervisor. "
        "CRITICAL ROUTING RULES:"
        "1. If the last message is a TEXT response from a worker (Technical_Analyst or Market_Researcher), you MUST output 'FINISH'."
        "2. ONLY route back to a worker if the user's request is strictly INCOMPLETE (e.g. asked for 2 stocks, only got 1)."
        "3. DO NOT output 'Technical_Analyst' just to say 'Is there anything else?'."
        "4. When in doubt, output 'FINISH'."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        ("system", "Who should act next? Select: Technical_Analyst, Market_Researcher, FINISH.")
    ])
    
    chain = prompt | llm.with_structured_output(RouteResponse)
    
    try:
        result = chain.invoke({"messages": messages})
        if not result or not result.next:
            return {"next": "FINISH"}
        return {"next": result.next}
    except Exception:
        return {"next": "FINISH"}

# --- 7. GUARDRAIL ---
def compliance_node(state):
    messages = state["messages"]
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and last_msg.content:
        risk_terms = ["buy", "sell", "invest", "guarantee", "profit"]
        if any(term in last_msg.content.lower() for term in risk_terms):
            disclaimer = "\n\n⚠️ **Compliance Notice:** AI-generated analysis. Not financial advice."
            return {"messages": [AIMessage(content=last_msg.content + disclaimer)]}
    return {"messages": []}

# --- 8. EDGES ---
def router(state):
    return state["next"]

def worker_router(state):
    # If tool called, go to tools. If text returned, go to Supervisor.
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "Supervisor"

def tool_router(state):
    return state["sender"]

workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Technical_Analyst", analyst_node)
workflow.add_node("Market_Researcher", researcher_node)
workflow.add_node("tools", ToolNode([get_cse_stock_price, web_search, get_technical_indicators]))
workflow.add_node("Compliance_Guardrail", compliance_node)

workflow.add_edge(START, "Supervisor")

workflow.add_conditional_edges("Supervisor", router, {
    "Technical_Analyst": "Technical_Analyst",
    "Market_Researcher": "Market_Researcher",
    "FINISH": "Compliance_Guardrail"
})

workflow.add_conditional_edges("Technical_Analyst", worker_router, {"tools": "tools", "Supervisor": "Supervisor"})
workflow.add_conditional_edges("Market_Researcher", worker_router, {"tools": "tools", "Supervisor": "Supervisor"})

workflow.add_conditional_edges("tools", tool_router, {
    "Technical_Analyst": "Technical_Analyst",
    "Market_Researcher": "Market_Researcher"
})

workflow.add_edge("Compliance_Guardrail", END)

graph = workflow.compile()