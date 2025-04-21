# test_api_keys.py
# Simple utility to test all API keys for the trading bot

import os
import requests
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api_test')

# Load environment variables
load_dotenv()

# API Keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

def test_alpaca_api():
    """Test Alpaca API connection"""
    try:
        import alpaca_trade_api as tradeapi
        
        print("\n=== Testing Alpaca API ===")
        print(f"API Key ID: {APCA_API_KEY_ID[:4]}...{APCA_API_KEY_ID[-4:]}")
        print(f"API Secret: {APCA_API_SECRET_KEY[:4]}...{APCA_API_SECRET_KEY[-4:]}")
        
        if not APCA_API_KEY_ID or not APCA_API_SECRET_KEY:
            print("[ERROR] Alpaca API keys not found in .env file")
            return False
        
        alpaca = tradeapi.REST(
            APCA_API_KEY_ID,
            APCA_API_SECRET_KEY,
            ALPACA_PAPER_URL,
            api_version='v2'
        )
        
        # Test account info
        account = alpaca.get_account()
        print(f"[SUCCESS] Successfully connected to Alpaca account: {account.id}")
        print(f"   Account status: {account.status}")
        print(f"   Cash balance: ${float(account.cash):.2f}")
        print(f"   Portfolio value: ${float(account.portfolio_value):.2f}")
        
        # Test market hours
        clock = alpaca.get_clock()
        market_status = "OPEN" if clock.is_open else "CLOSED"
        print(f"[SUCCESS] Market is currently {market_status}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Alpaca API Error: {e}")
        return False

def test_openai_api():
    """Test OpenAI API connection"""
    try:
        print("\n=== Testing OpenAI API ===")
        api_key = OPENAI_API_KEY
        
        if not api_key:
            print("[ERROR] OpenAI API key not found in .env file")
            return False
        
        # Only show first and last 4 characters of the key for security
        print(f"API Key: {api_key[:4]}...{api_key[-4:]}")
        
        # Initialize the client
        client = OpenAI(api_key=api_key)
        
        # Make a simple API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello"}
            ],
            max_tokens=10
        )
        
        response_text = response.choices[0].message.content
        print(f"[SUCCESS] Successfully called OpenAI API")
        print(f"   Response: '{response_text}'")
        
        # Get available models
        models = client.models.list()
        print(f"[SUCCESS] Available models include: {', '.join([model.id for model in models.data[:3]])}...")
        
        return True
    except Exception as e:
        print(f"[ERROR] OpenAI API Error: {e}")
        return False

def test_news_api():
    """Test News API connection"""
    try:
        print("\n=== Testing News API ===")
        api_key = NEWS_API_KEY
        
        if not api_key:
            print("[ERROR] News API key not found in .env file")
            return False
        
        # Only show first and last 4 characters of the key for security
        print(f"API Key: {api_key[:4]}...{api_key[-4:]}")
        
        # Make a simple API call
        url = f"https://newsapi.org/v2/everything?q=AAPL&language=en&pageSize=1&apiKey={api_key}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"[SUCCESS] Successfully called News API")
            print(f"   Total results: {data.get('totalResults', 0)}")
            if articles:
                print(f"   Sample headline: '{articles[0].get('title')}'")
            return True
        else:
            print(f"[ERROR] News API Error: Status code {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[ERROR] News API Error: {e}")
        return False

def main():
    """Main function to test all APIs"""
    print("=== Trading Bot API Key Test Utility ===")
    print("Testing all API connections required by the trading bot...")
    
    alpaca_success = test_alpaca_api()
    openai_success = test_openai_api()
    news_success = test_news_api()
    
    print("\n=== Summary ===")
    print(f"Alpaca API: {'[SUCCESS] Working' if alpaca_success else '[ERROR] Failed'}")
    print(f"OpenAI API: {'[SUCCESS] Working' if openai_success else '[ERROR] Failed'}")
    print(f"News API: {'[SUCCESS] Working' if news_success else '[ERROR] Failed'}")
    
    if alpaca_success and openai_success and news_success:
        print("\n[SUCCESS] All API keys are working correctly!")
        print("[SUCCESS] The trading bot should be able to run without API issues.")
    else:
        print("\n[ERROR] Some API keys are not working.")
        print("[ERROR] Please fix the issues above before running the trading bot.")
    
if __name__ == "__main__":
    main()