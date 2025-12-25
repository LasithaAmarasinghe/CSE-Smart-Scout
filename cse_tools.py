import os 
import requests
import random
from datetime import datetime
from dotenv import load_dotenv
from tavily import TavilyClient
from difflib import get_close_matches

# --- CONFIGURATION ---
load_dotenv()
# Ensure TAVILY_API_KEY is in your .env
api_key = os.getenv("TAVILY_API_KEY")

# --- KNOWLEDGE BASE ---
CSE_TICKER_MAP = {
    "john keells": "JKH", "jkh": "JKH", "keells": "JKH",
    "dialog": "DIAL", "dialog axiata": "DIAL",
    "commercial bank": "COMB", "comb": "COMB",
    "sampath": "SAMP", "sampath bank": "SAMP",
    "hatton": "HNB", "hnb": "HNB",
    "hayleys": "HAYL", "sri lanka telecom": "SLTL",
    "lanka ioc": "LIOC", "melstacorp": "MELS",
    "lolc": "LOLC", "hemas": "HHL", "access engineering": "AEL",
    "softlogic": "SHL"
}

def resolve_ticker(user_input: str) -> str:
    """Smart lookup for tickers."""
    clean_input = user_input.lower().strip()
    if clean_input in CSE_TICKER_MAP:
        return CSE_TICKER_MAP[clean_input]
    matches = get_close_matches(clean_input, CSE_TICKER_MAP.keys(), n=1, cutoff=0.6)
    if matches:
        return CSE_TICKER_MAP[matches[0]]
    return user_input.upper()

def get_cse_stock_price(ticker: str):
    """Fetches real-time price from CSE."""
    clean_ticker = resolve_ticker(ticker)
    cse_symbol = f"{clean_ticker}.N0000" if not clean_ticker.endswith(".N0000") else clean_ticker
    
    print(f"DEBUG: 🔍 Fetching Price for {cse_symbol}...")
    url = "https://www.cse.lk/api/companyInfoSummery"
    
    try:
        response = requests.post(
            url, 
            data={"symbol": cse_symbol}, 
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        if response.status_code != 200: raise ValueError("CSE API Error")
        
        data = response.json()
        info = data.get('reqSymbolInfo', {})
        if not info: raise ValueError("No data found")

        return {
            "symbol": cse_symbol,
            "price": info.get('lastTradedPrice'),
            "change": info.get('change'),
            "percent_change": info.get('changePercentage'),
            "currency": "LKR",
            "status": "Active"
        }
    except Exception:
        return _generate_mock_data(ticker)

def get_technical_indicators(ticker: str):
    """
    [NEW] Simulates ATrad's technical analysis engine.
    Calculates RSI and MACD (Mocked for demo).
    """
    clean_ticker = resolve_ticker(ticker)
    # Mocking technical data
    rsi = round(random.uniform(30, 80), 2)
    sentiment = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
    
    return {
        "ticker": clean_ticker,
        "RSI_14": rsi,
        "RSI_Signal": sentiment,
        "MACD": "Bullish Crossover" if rsi > 50 else "Bearish Divergence",
        "Support_Level": round(random.uniform(50, 100), 2),
        "Resistance_Level": round(random.uniform(100, 150), 2)
    }

def _generate_mock_data(ticker):
    return {
        "symbol": ticker.upper(),
        "price": round(random.uniform(50, 200), 2),
        "source": "Mock Data (Fallback)"
    }

def web_search(query: str):
    """
    Searches using Tavily. 
    (Renamed from search_market_news to fix LLM hallucination)
    """
    print(f"DEBUG: 🌐 Tavily Search for: '{query}'...")
    
    try:
        tavily = TavilyClient(api_key=api_key)
        
        # We append "Sri Lanka" to ensure context
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