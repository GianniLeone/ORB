# scheduler.py
# Handles scheduling and continuous operation of the trading bot

import os
import time
import logging
import datetime
import importlib
import signal
import sys
from pathlib import Path
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Import timezone utilities
try:
    from timezone_utils import get_eastern_time, get_current_market_period, log_current_time
    TIMEZONE_UTILS_AVAILABLE = True
except ImportError:
    TIMEZONE_UTILS_AVAILABLE = False

# Configuration (defined BEFORE logging setup)
CONFIG = {
    "trading_bot_module": "direct_news_trader",  # Python module name (without .py)
    "trading_bot_function": "main",              # Function to run in the module
    "max_retries": 3,                            # Max retries on failure
    "retry_delay_seconds": 60,                   # Delay between retries
    "enable_after_hours_trading": True,          # Whether to queue trades outside market hours
    "enable_weekend_checks": False,              # Whether to run on weekends
    # Smart scheduling intervals (in minutes)
    "check_intervals": {
        "4am-9am": 15,     # Pre-market (high)
        "9am-12pm": 5,     # Market open (very high)
        "12pm-3pm": 30,    # Midday (medium)
        "3pm-4pm": 10,     # Power hour (high)
        "4pm-6pm": 20,     # After-hours reaction (medium)
        "6pm-12am": 45,    # Evening (low)
        "12am-4am": 90     # Overnight (very low)
    }
}

# Configure logging (AFTER configuration is defined)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bot_scheduler')

# Add a summary of the check intervals
logger.info("=== Smart News Scheduling Strategy ===")
logger.info("Time periods and polling frequencies:")
logger.info("4am-9am: Every %d minutes (Pre-market)", CONFIG["check_intervals"]["4am-9am"])
logger.info("9am-12pm: Every %d minutes (Market open)", CONFIG["check_intervals"]["9am-12pm"])
logger.info("12pm-3pm: Every %d minutes (Midday)", CONFIG["check_intervals"]["12pm-3pm"])
logger.info("3pm-4pm: Every %d minutes (Power hour)", CONFIG["check_intervals"]["3pm-4pm"])
logger.info("4pm-6pm: Every %d minutes (After-hours reaction)", CONFIG["check_intervals"]["4pm-6pm"])
logger.info("6pm-12am: Every %d minutes (Evening)", CONFIG["check_intervals"]["6pm-12am"])
logger.info("12am-4am: Every %d minutes (Overnight)", CONFIG["check_intervals"]["12am-4am"])
logger.info("Expected daily API calls: ~96 calls/day")
logger.info("=======================================")

# Load environment variables
load_dotenv()

# Alpaca API credentials
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Initialize Alpaca API
alpaca = tradeapi.REST(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_PAPER_URL,
    api_version='v2'
)

def is_market_open():
    """Check if the market is currently open using Alpaca API"""
    try:
        clock = alpaca.get_clock()
        return clock.is_open
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        # Default to closed if we can't check
        return False

def get_market_hours():
    """Get today's market open and close times"""
    try:
        calendar = alpaca.get_calendar()
        today = datetime.date.today().isoformat()
        
        # Find today in the calendar
        for day in calendar:
            if day.date.isoformat() == today:
                return {
                    "open": day.open,
                    "close": day.close,
                    "is_open": True
                }
        
        # If not found, market is closed today
        return {
            "open": None,
            "close": None,
            "is_open": False
        }
    except Exception as e:
        logger.error(f"Error getting market hours: {e}")
        # Return default hours if we can't check
        now = datetime.datetime.now()
        return {
            "open": now.replace(hour=9, minute=30, second=0),
            "close": now.replace(hour=16, minute=0, second=0),
            "is_open": False
        }

def is_trading_day():
    """Check if today is a trading day (weekday and not a market holiday)"""
    # Check if it's a weekend
    now = datetime.datetime.now()
    if now.weekday() >= 5 and not CONFIG["enable_weekend_checks"]:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Check if it's a market holiday using Alpaca's calendar
    try:
        market_hours = get_market_hours()
        return market_hours["is_open"]
    except Exception as e:
        logger.error(f"Error checking if today is a trading day: {e}")
        # Default to True for weekdays if we can't check
        return now.weekday() < 5

def get_interval_for_current_time():
    """
    Determine the appropriate polling interval based on the current time (Eastern Time)
    
    Returns:
        int: Interval in minutes for the current time period
    """
    # Use timezone utilities if available
    if TIMEZONE_UTILS_AVAILABLE:
        period_key, period_name, interval = get_current_market_period()
        logger.info(f"Current time period: {period_key} ({period_name}), interval: {interval} minutes")
        return interval
        
    # Fallback to the old method if timezone utilities are not available
    # Get current time (in Eastern Time)
    now = datetime.datetime.now()
    
    # Rough conversion to Eastern Time (ET is UTC-4 in summer, UTC-5 in winter)
    # For more accuracy, use the pytz library
    hour_offset = 4  # Adjust this value based on daylight savings time
    current_hour_et = (now.hour - hour_offset) % 24
    
    # Determine the appropriate interval based on time of day
    if 4 <= current_hour_et < 9:       # 4am-9am (pre-market)
        interval = CONFIG["check_intervals"]["4am-9am"]
        period = "4am-9am (Pre-market)"
    elif 9 <= current_hour_et < 12:     # 9am-12pm (market open)
        interval = CONFIG["check_intervals"]["9am-12pm"]
        period = "9am-12pm (Market open)"
    elif 12 <= current_hour_et < 15:    # 12pm-3pm (midday)
        interval = CONFIG["check_intervals"]["12pm-3pm"]
        period = "12pm-3pm (Midday)"
    elif 15 <= current_hour_et < 16:    # 3pm-4pm (power hour)
        interval = CONFIG["check_intervals"]["3pm-4pm"]
        period = "3pm-4pm (Power hour)"
    elif 16 <= current_hour_et < 18:    # 4pm-6pm (after-hours reaction)
        interval = CONFIG["check_intervals"]["4pm-6pm"]
        period = "4pm-6pm (After-hours)"
    elif 18 <= current_hour_et < 24:    # 6pm-12am (evening)
        interval = CONFIG["check_intervals"]["6pm-12am"]
        period = "6pm-12am (Evening)"
    else:                               # 12am-4am (overnight)
        interval = CONFIG["check_intervals"]["12am-4am"]
        period = "12am-4am (Overnight)"
    
    logger.info(f"Current time period: {period}, interval: {interval} minutes")
    return interval

def should_run_now():
    """Determine if the bot should run now based on time and configuration"""
    now = datetime.datetime.now()
    
    # For news monitoring, we run every day, regardless of trading day status
    # We just check if enough time has passed since the last run
    
    # Check if enough time has passed since last run
    last_run_file = Path("data/last_run.txt")
    if last_run_file.exists():
        with open(last_run_file, "r") as f:
            last_run_str = f.read().strip()
            last_run = datetime.datetime.fromisoformat(last_run_str)
            minutes_since_last_run = (now - last_run).total_seconds() / 60
            
            # Get the appropriate interval based on current time
            appropriate_interval = get_interval_for_current_time()
            
            if minutes_since_last_run < appropriate_interval:
                logger.info(f"Not enough time since last run ({minutes_since_last_run:.2f} minutes), skipping")
                return False
    
    return True

def update_last_run_time():
    """Update the timestamp of the last bot run"""
    Path("data").mkdir(exist_ok=True)
    now = datetime.datetime.now()
    with open("data/last_run.txt", "w") as f:
        f.write(now.isoformat())
    logger.info(f"Updated last run time to {now.isoformat()}")

def run_trading_bot():
    """Run the trading bot module"""
    try:
        # Import the trading bot module
        bot_module = importlib.import_module(CONFIG["trading_bot_module"])
        
        # Get the main function
        main_function = getattr(bot_module, CONFIG["trading_bot_function"])
        
        # Run the bot
        logger.info(f"Running trading bot: {CONFIG['trading_bot_module']}.{CONFIG['trading_bot_function']}()")
        result = main_function()
        
        # Update the last run time
        update_last_run_time()
        
        return result
    except Exception as e:
        logger.error(f"Error running trading bot: {e}")
        return None

def run_with_retries():
    """Run the trading bot with retries on failure"""
    for attempt in range(CONFIG["max_retries"]):
        try:
            result = run_trading_bot()
            
            if result is not None:
                logger.info("Trading bot run successful")
                return True
            
            logger.warning(f"Trading bot returned None (attempt {attempt+1}/{CONFIG['max_retries']})")
        except Exception as e:
            logger.error(f"Error in trading bot (attempt {attempt+1}/{CONFIG['max_retries']}): {e}")
        
        # Don't delay on the last attempt
        if attempt < CONFIG["max_retries"] - 1:
            logger.info(f"Waiting {CONFIG['retry_delay_seconds']} seconds before retrying...")
            time.sleep(CONFIG["retry_delay_seconds"])
    
    logger.error(f"Trading bot failed after {CONFIG['max_retries']} attempts")
    return False

def handle_exit(signum, frame):
    """Handle exit signals gracefully"""
    logger.info("Received exit signal, shutting down...")
    sys.exit(0)

def main_loop():
    """Main scheduler loop"""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    logger.info("Starting trading bot scheduler with smart scheduling")
    
    # Create data directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)
    
    # Log timezone information if available
    if TIMEZONE_UTILS_AVAILABLE:
        log_current_time()
    else:
        logger.warning("Timezone utilities not available. Using approximate Eastern Time conversion.")
        logger.warning("Install pytz and create timezone_utils.py for more accurate timezone handling.")
    
    # Track daily API calls (for monitoring)
    daily_calls = 0
    current_day = datetime.datetime.now().day
    
    try:
        while True:
            try:
                # Reset daily calls counter if day changed
                now = datetime.datetime.now()
                if now.day != current_day:
                    logger.info(f"New day started, resetting API call counter (was {daily_calls})")
                    daily_calls = 0
                    current_day = now.day
                
                # Check if we should run now
                if should_run_now():
                    logger.info("Running trading bot")
                    run_with_retries()
                    
                    # Increment API call counter
                    daily_calls += 1
                    logger.info(f"Daily API calls so far: {daily_calls}/96")
                else:
                    logger.info("Skipping run based on schedule")
                
                # Calculate time until next check
                next_check_minutes = get_interval_for_current_time()
                
                logger.info(f"Waiting {next_check_minutes} minutes until next check")
                time.sleep(next_check_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait before trying again
                time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Unhandled error in scheduler: {e}")
        raise

if __name__ == "__main__":
    main_loop()