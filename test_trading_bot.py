# test_trading_bot.py
# Test script for the ORB News Trading Bot

import os
import sys
import json
import logging
import datetime
from pathlib import Path
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('test_bot')

# Load environment variables
load_dotenv()

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Other API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def check_environment():
    """Check if the environment is set up correctly"""
    logger.info("Checking environment...")
    
    # Check Python version
    python_version = sys.version.split()[0]
    logger.info(f"Python version: {python_version}")
    
    # Check if required modules are installed
    required_modules = [
        "alpaca_trade_api",
        "openai",
        "requests",
        "python-dotenv",
        "pytz",
        "pandas",
        "numpy"
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"[PASS] Module {module} is installed")
        except ImportError:
            missing_modules.append(module)
            logger.error(f"[FAIL] Module {module} is NOT installed")
    
    if missing_modules:
        logger.error(f"Missing modules: {', '.join(missing_modules)}")
        logger.error("Please install missing modules with: pip install " + " ".join(missing_modules))
    else:
        logger.info("All required modules are installed")
    
    # Check API keys
    api_keys = {
        "ALPACA_API_KEY": ALPACA_API_KEY,
        "ALPACA_SECRET_KEY": ALPACA_SECRET_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "NEWS_API_KEY": NEWS_API_KEY
    }
    
    missing_keys = []
    for key_name, key_value in api_keys.items():
        if not key_value:
            missing_keys.append(key_name)
            logger.error(f"[FAIL] {key_name} is not set")
        else:
            # Mask the key value for security
            masked_value = key_value[:4] + "*" * (len(key_value) - 8) + key_value[-4:]
            logger.info(f"[PASS] {key_name} is set: {masked_value}")
    
    if missing_keys:
        logger.error(f"Missing API keys: {', '.join(missing_keys)}")
        logger.error("Please set these environment variables in your .env file")
    else:
        logger.info("All required API keys are set")
    
    # Check directory structure
    required_dirs = [
        "data",
        "data/orders",
        "data/orb_data",
        "logs"
    ]
    
    missing_dirs = []
    for directory in required_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            missing_dirs.append(directory)
            logger.error(f"[FAIL] Directory {directory} does not exist")
        else:
            logger.info(f"[PASS] Directory {directory} exists")
    
    if missing_dirs:
        logger.info("Creating missing directories...")
        for directory in missing_dirs:
            Path(directory).mkdir(exist_ok=True, parents=True)
            logger.info(f"Created directory {directory}")
    
    # Check if required scripts exist
    required_scripts = [
        "orb_news_trader.py",
        "orb_news_scheduler.py",
        "trading_bot_service.py"
    ]
    
    missing_scripts = []
    for script in required_scripts:
        script_path = Path(script)
        if not script_path.exists():
            missing_scripts.append(script)
            logger.error(f"[FAIL] Script {script} does not exist")
        else:
            logger.info(f"[PASS] Script {script} exists")
    
    if missing_scripts:
        logger.error(f"Missing scripts: {', '.join(missing_scripts)}")
        return False
    
    logger.info("Environment check completed")
    return True

def test_alpaca_connection():
    """Test connection to Alpaca API"""
    logger.info("Testing Alpaca API connection...")
    
    try:
        # Initialize Alpaca API
        api = tradeapi.REST(
            ALPACA_API_KEY,
            ALPACA_SECRET_KEY,
            ALPACA_PAPER_URL,
            api_version='v2'
        )
        
        # Get account info
        account = api.get_account()
        logger.info(f"[PASS] Connected to Alpaca account: {account.id}")
        logger.info(f"Account type: {'Paper' if account.id.startswith('paper') else 'Live'}")
        logger.info(f"Cash balance: ${float(account.cash):.2f}")
        logger.info(f"Portfolio value: ${float(account.portfolio_value):.2f}")
        logger.info(f"Buying power: ${float(account.buying_power):.2f}")
        
        # Check market status
        clock = api.get_clock()
        market_status = "open" if clock.is_open else "closed"
        next_open = clock.next_open.strftime("%Y-%m-%d %H:%M:%S")
        next_close = clock.next_close.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"Market is currently {market_status}")
        logger.info(f"Next market open: {next_open}")
        logger.info(f"Next market close: {next_close}")
        
        # Get positions
        positions = api.list_positions()
        logger.info(f"Current positions: {len(positions)}")
        for position in positions:
            logger.info(f"  - {position.symbol}: {position.qty} shares @ ${float(position.avg_entry_price):.2f}, " +
                        f"current value: ${float(position.market_value):.2f}")
        
        return True
    except Exception as e:
        logger.error(f"[FAIL] Error connecting to Alpaca API: {e}")
        return False

def test_news_api():
    """Test connection to NewsAPI"""
    logger.info("Testing NewsAPI connection...")
    
    if not NEWS_API_KEY:
        logger.error("[FAIL] NEWS_API_KEY is not set")
        return False
    
    try:
        import requests
        
        # Sample query
        url = f"https://newsapi.org/v2/everything?q=stock+market&language=en&pageSize=1&apiKey={NEWS_API_KEY}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            
            if articles:
                article = articles[0]
                logger.info(f"[PASS] NewsAPI connection successful")
                logger.info(f"Sample article: {article.get('title', 'No title')}")
                return True
            else:
                logger.warning("[WARN] NewsAPI returned no articles")
                return True
        else:
            logger.error(f"[FAIL] NewsAPI error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"[FAIL] Error connecting to NewsAPI: {e}")
        return False

def test_openai_api():
    """Test connection to OpenAI API"""
    logger.info("Testing OpenAI API connection...")
    
    if not OPENAI_API_KEY:
        logger.error("[FAIL] OPENAI_API_KEY is not set")
        return False
    
    try:
        from openai import OpenAI
        
        # Initialize OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Simple test request
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'API connection successful' in one short sentence."}
            ],
            max_tokens=20
        )
        
        content = response.choices[0].message.content
        logger.info(f"[PASS] OpenAI API connection successful")
        logger.info(f"Response: {content}")
        
        return True
    except Exception as e:
        logger.error(f"[FAIL] Error connecting to OpenAI API: {e}")
        return False

def test_orb_trader_import():
    """Test importing the ORB trader module"""
    logger.info("Testing ORB trader module import...")
    
    try:
        import orb_news_trader
        logger.info(f"[PASS] Successfully imported orb_news_trader module")
        
        # Check if main function exists
        if hasattr(orb_news_trader, 'main'):
            logger.info(f"[PASS] Module has main() function")
        else:
            logger.warning(f"[WARN] Module does not have main() function")
        
        return True
    except Exception as e:
        logger.error(f"[FAIL] Error importing orb_news_trader module: {e}")
        return False

def run_tests():
    """Run all tests"""
    logger.info("Starting tests...")
    
    # Create test results dictionary
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "tests": {}
    }
    
    # Check environment
    results["tests"]["environment"] = check_environment()
    
    # Test Alpaca connection
    results["tests"]["alpaca_api"] = test_alpaca_connection()
    
    # Test NewsAPI connection
    results["tests"]["news_api"] = test_news_api()
    
    # Test OpenAI API connection
    results["tests"]["openai_api"] = test_openai_api()
    
    # Test ORB trader import
    results["tests"]["orb_trader_import"] = test_orb_trader_import()
    
    # Calculate overall result
    results["all_passed"] = all(results["tests"].values())
    
    # Save results
    try:
        with open("test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Test results saved to test_results.json")
    except Exception as e:
        logger.error(f"Error saving test results: {e}")
    
    # Print summary
    logger.info("\nTEST SUMMARY:")
    for test_name, test_result in results["tests"].items():
        status = "[PASS]" if test_result else "[FAIL]"
        logger.info(f"{test_name}: {status}")
    
    overall = "[PASS] ALL TESTS PASSED" if results["all_passed"] else "[FAIL] SOME TESTS FAILED"
    logger.info(f"\nOVERALL RESULT: {overall}")
    
    if not results["all_passed"]:
        logger.info("\nPlease fix the issues above before running the trading bot.")
    else:
        logger.info("\nAll tests passed! You can now run the trading bot with:")
        logger.info("  python orb_news_trader.py")
        logger.info("Or install it as a service using:")
        logger.info("  python trading_bot_service.py install")
        logger.info("  python trading_bot_service.py start")
    
    return results["all_passed"]

if __name__ == "__main__":
    run_tests()