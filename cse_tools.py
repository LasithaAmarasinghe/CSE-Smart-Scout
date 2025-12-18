import os 
import requests
import json
import random
from datetime import datetime
from dotenv import load_dotenv
from tavily import TavilyClient # Ensure you pip installed this: pip install tavily-python
from difflib import get_close_matches

# --- CONFIGURATION ---

load_dotenv()
api_key = os.getenv("TAVILY_API_KEY")

# --- KNOWLEDGE BASE ---
# A mapping of common names/keywords to their CSE Ticker
CSE_TICKER_MAP = {
    "john keells": "JKH",
    "jkh": "JKH",
    "keells": "JKH",
    "dialog": "DIAL",
    "dialog axiata": "DIAL",
    "commercial bank": "COMB",
    "comb": "COMB",
    "sampath": "SAMP",
    "sampath bank": "SAMP",
    "hatton": "HNB",
    "hnb": "HNB",
    "hayleys": "HAYL",
    "sri lanka telecom": "SLTL",
    "slt": "SLTL",
    "lanka ioc": "LIOC",
    "lioc": "LIOC",
    "melstacorp": "MELS",
    "lolc": "LOLC",
    "hemas": "HHL",
    "access engineering": "AEL",
    "softlogic": "SHL"
}

def resolve_ticker(user_input: str) -> str:
    """
    Smartly converts 'John Keells' -> 'JKH'.
    Uses exact lookup first, then fuzzy matching.
    """
    clean_input = user_input.lower().strip()
    
    # 1. Direct Lookup
    if clean_input in CSE_TICKER_MAP:
        return CSE_TICKER_MAP[clean_input]
    
    # 2. Fuzzy Match (Finds 'Dialog' if user types 'Dialg')
    matches = get_close_matches(clean_input, CSE_TICKER_MAP.keys(), n=1, cutoff=0.6)
    if matches:
        return CSE_TICKER_MAP[matches[0]]
    
    # 3. Fallback: Assume the user actually typed a ticker (e.g. 'DIST')
    return user_input.upper()


def get_cse_stock_price(ticker: str):
    """
    Fetches stock price from CSE with 'Stealth Mode'.
    """
    # 1. Resolve the name (e.g., "John Keells" -> "JKH")
    clean_ticker = resolve_ticker(ticker)
    
    # 2. Add Suffix SAFELY (The Fix)
    # Check if it already has the suffix to prevent "JKH.N0000.N0000"
    if not clean_ticker.endswith(".N0000"):
        cse_symbol = f"{clean_ticker}.N0000"
    else:
        cse_symbol = clean_ticker
        
    # Standardize to uppercase just in case
    cse_symbol = cse_symbol.upper()
    
    print(f"DEBUG: 🔍 Hitting CSE Official API for {cse_symbol}...")

    url = "https://www.cse.lk/api/companyInfoSummery"
    payload = {"symbol": cse_symbol}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cse.lk/",
        "Origin": "https://www.cse.lk",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=5)
        
        if response.status_code != 200:
            raise ValueError(f"Status {response.status_code}")

        data = response.json()
        info = data.get('reqSymbolInfo', {})
        
        if not info:
             raise ValueError("Symbol data empty")

        price = info.get('lastTradedPrice')
        
        return {
            "symbol": cse_symbol,
            "price": price,
            "change_amount": info.get('change'),
            "change_percent": info.get('changePercentage'),
            "currency": "LKR",
            "market_status": "Active (CSE Direct)",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        print(f"⚠️ API ERROR: {e}. Switching to Mock Data.")
        return _generate_mock_data(ticker)

def _generate_mock_data(ticker):
    base_price = random.uniform(50, 200)
    change = random.uniform(-5, 5)
    return {
        "symbol": ticker.upper(),
        "price": round(base_price, 2),
        "currency": "LKR",
        "source": "Mock Data (Fallback)"
    }

def search_market_news(query: str):
    """
    Searches using Tavily with the key defined locally.
    """
    print(f"DEBUG: 🌐 Tavily Search for: '{query}'...")
    
    try:
        # We use the key defined at the top of the file
        tavily = TavilyClient(api_key=api_key)
        
        response = tavily.search(
            query=f"{query} Sri Lanka stock market", 
            search_depth="basic",
            max_results=3,
            topic="news" 
        )
        
        context = []
        for result in response.get('results', []):
            context.append(f"- {result['title']}: {result['content']}")
            
        if not context:
            return "No news found via Tavily."
            
        return "\n".join(context)

    except Exception as e:
        print(f"⚠️ TAVILY ERROR: {e}")
        return "News search failed. Please verify API Key."

def get_market_overview():
    """
    Fetches the current Top 5 companies by Market Cap.
    """
    print("DEBUG: 🌐 Fetching Top 5 List...")
    
    tavily = TavilyClient(api_key=api_key)
    # We use a very specific query to get a table/list result
    response = tavily.search(
        query="largest listed companies Sri Lanka CSE market capitalization list 2025", 
        search_depth="advanced",
        topic="news"
    )
    
    summary = "Current Market Leaders (Source: Tavily):\n"
    for result in response.get('results', []):
        summary += f"- {result['title']}: {result['content']}\n"
        
    return summary

# --- TEST BLOCK ---
if __name__ == "__main__":
    # Run this file directly to test if your key works!
    print(search_market_news("JKH"))