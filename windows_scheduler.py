# windows_scheduler.py
# Simple Windows-compatible scheduler for the ORB News Trading Bot

import os
import sys
import time
import logging
import datetime
import importlib
from pathlib import Path
import pytz
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("windows_scheduler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('windows_scheduler')

# Import timezone utilities
try:
    from timezone_utils import get_eastern_time, get_current_market_period, log_current_time
    TIMEZONE_UTILS_AVAILABLE = True
    logger.info("Timezone utilities loaded successfully")
except ImportError:
    TIMEZONE_UTILS_AVAILABLE = False
    logger.warning("Timezone utilities not available, using built-in timezone functions")

# Load environment variables
load_dotenv()

# Alpaca API credentials
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
ALPACA_PAPER_URL = os.getenv("ALPACA_PAPER_URL", "https://paper-api.alpaca.markets")

# Initialize Alpaca API
alpaca = tradeapi.REST(
    APCA_API_KEY_ID,
    APCA_API_SECRET_KEY,
    ALPACA_PAPER_URL,
    api_version='v2'
)

# Import timezone utilities
try:
    from timezone_utils import get_eastern_time, get_current_market_period, log_current_time
    TIMEZONE_UTILS_AVAILABLE = True
    logger.info("Timezone utilities loaded successfully")
except ImportError:
    TIMEZONE_UTILS_AVAILABLE = False
    logger.warning("Timezone utilities not available, using built-in timezone functions")

# Configuration
CONFIG = {
    "trading_bot_module": "windows_trader",  # Python module name (without .py)
    "trading_bot_function": "main",          # Function to run in the module
    "max_retries": 3,                        # Max retries on failure
    "retry_delay_seconds": 60,               # Delay between retries
    
    # Check intervals in minutes based on market periods
    "check_intervals": {
        "pre_market": 15,      # 4am-9:30am (Pre-market)
        "market_open": 5,       # 9:30am-10:30am (Market open + ORB period)
        "morning": 15,          # 10:30am-12pm (Morning session)
        "midday": 30,           # 12pm-2pm (Midday lull)
        "afternoon": 15,        # 2pm-3pm (Afternoon session)
        "power_hour": 10,       # 3pm-4pm (Power hour)
        "after_hours": 20,      # 4pm-8pm (After-hours)
        "evening": 45,          # 8pm-12am (Evening)
        "overnight": 90         # 12am-4am (Overnight)
    }
}

# Flag to control the scheduler
running = True

def get_eastern_time():
    """Get current time in US Eastern Time (ET), which is the timezone for US markets"""
    if TIMEZONE_UTILS_AVAILABLE:
        # Use the imported function
        from timezone_utils import get_eastern_time as get_et
        et_time = get_et()
        logger.debug(f"Using timezone_utils.get_eastern_time(): {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return et_time
    else:
        # Fallback implementation
        utc_now = datetime.datetime.now(pytz.UTC)
        eastern = pytz.timezone('US/Eastern')
        eastern_time = utc_now.astimezone(eastern)
        
        # Log for debugging
        is_dst = eastern_time.dst() != datetime.timedelta(0)
        logger.debug(f"Fallback timezone calculation:")
        logger.debug(f"UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.debug(f"Eastern time: {eastern_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.debug(f"Is DST active: {is_dst}")
        
        return eastern_time

def is_market_open():
    """Check if the market is currently open using Alpaca API"""
    try:
        clock = alpaca.get_clock()
        is_open = clock.is_open
        
        # Log current time for debugging
        et_now = get_eastern_time()
        logger.debug(f"Current ET time: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.debug(f"Market is {'open' if is_open else 'closed'}")
        
        return is_open
    except Exception as e:
        logger.error(f"Error checking market hours: {e}")
        # Default to closed if we can't check
        return False

def is_trading_day():
    """Check if today is a trading day (weekday and not a market holiday)"""
    # Get current Eastern Time
    et_now = get_eastern_time()
    
    # Check if it's a weekend in ET
    if et_now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        logger.info(f"Not a trading day: It's {et_now.strftime('%A')} in ET")
        return False
    
    # Check if it's a market holiday using Alpaca's calendar
    try:
        calendar = alpaca.get_calendar()
        today = et_now.date().isoformat()
        
        for day in calendar:
            if day.date.isoformat() == today:
                logger.info(f"Today ({today}) is a trading day according to Alpaca calendar")
                return True
        
        # If today is not in the calendar, it's a holiday
        logger.info(f"Today ({today}) is not a trading day according to Alpaca calendar (likely a holiday)")
        return False
    except Exception as e:
        logger.error(f"Error checking if today is a trading day: {e}")
        # Default to True for weekdays if we can't check
        return et_now.weekday() < 5

def get_current_market_period():
    """Determine the current market period based on Eastern Time"""
    if TIMEZONE_UTILS_AVAILABLE:
        # Use the imported function
        from timezone_utils import get_current_market_period as get_period
        period_key, period_name, interval = get_period()
        logger.debug(f"Using timezone_utils: Current period: {period_key} ({period_name})")
        return period_key
    else:
        # Fallback implementation
        # Get current Eastern Time
        et_now = get_eastern_time()
        et_hour = et_now.hour
        et_minute = et_now.minute
        
        logger.debug(f"Fallback market period calculation:")
        logger.debug(f"Current ET hour: {et_hour}, minute: {et_minute}")
        
        # Determine the period based on time
        if 4 <= et_hour < 9 or (et_hour == 9 and et_minute < 30):
            return "pre_market"
        elif (et_hour == 9 and et_minute >= 30) or (et_hour == 10 and et_minute < 30):
            return "market_open"
        elif (et_hour == 10 and et_minute >= 30) or (et_hour == 11):
            return "morning"
        elif 12 <= et_hour < 14:
            return "midday"
        elif 14 <= et_hour < 15:
            return "afternoon"
        elif 15 <= et_hour < 16:
            return "power_hour"
        elif 16 <= et_hour < 20:
            return "after_hours"
        elif 20 <= et_hour < 24:
            return "evening"
        else:  # 0 <= et_hour < 4
            return "overnight"

def should_run_now():
    """Determine if the bot should run now based on time and configuration"""
    # Check if enough time has passed since last run
    last_run_file = Path("data/last_run.txt")
    if last_run_file.exists():
        try:
            with open(last_run_file, "r") as f:
                last_run_str = f.read().strip()
                last_run = datetime.datetime.fromisoformat(last_run_str)
                now = datetime.datetime.now()
                minutes_since_last_run = (now - last_run).total_seconds() / 60
                
                # Get the appropriate interval based on current time
                period = get_current_market_period()
                appropriate_interval = CONFIG["check_intervals"][period]
                
                # Get current Eastern Time for debugging
                et_now = get_eastern_time()
                
                logger.info(f"Current time (ET): {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logger.info(f"Current period: {period}, interval: {appropriate_interval} minutes")
                logger.info(f"Minutes since last run: {minutes_since_last_run:.2f}")
                
                if minutes_since_last_run < appropriate_interval:
                    logger.info(f"Not enough time since last run, skipping")
                    return False
        except Exception as e:
            logger.error(f"Error reading last run time: {e}")
            # If there's an error reading the last run time, proceed with execution
            return True
    
    return True

def update_last_run_time():
    """Update the timestamp of the last bot run"""
    Path("data").mkdir(exist_ok=True)
    now = datetime.datetime.now()
    try:
        with open("data/last_run.txt", "w") as f:
            f.write(now.isoformat())
        logger.info(f"Updated last run time to {now.isoformat()}")
    except Exception as e:
        logger.error(f"Error updating last run time: {e}")

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
            time.sleep(CONFIG['retry_delay_seconds'])
    
    logger.error(f"Trading bot failed after {CONFIG['max_retries']} attempts")
    return False

def log_status():
    """Log current system status"""
    et_now = get_eastern_time()
    market_open = is_market_open()
    trading_day = is_trading_day()
    current_period = get_current_market_period()
    appropriate_interval = CONFIG["check_intervals"][current_period]
    
    logger.info("=== System Status ===")
    logger.info(f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Current ET time: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')} (DST active: {et_now.dst() != datetime.timedelta(0)})")
    logger.info(f"Market is {'open' if market_open else 'closed'}")
    logger.info(f"Today is {'a trading day' if trading_day else 'not a trading day'}")
    logger.info(f"Current period: {current_period}, check interval: {appropriate_interval} minutes")
    
    # Check portfolio status if market is open
    if market_open:
        try:
            account = alpaca.get_account()
            positions = alpaca.list_positions()
            
            logger.info(f"Portfolio value: ${float(account.portfolio_value):.2f}")
            logger.info(f"Cash balance: ${float(account.cash):.2f}")
            logger.info(f"Number of positions: {len(positions)}")
        except Exception as e:
            logger.error(f"Error getting portfolio status: {e}")

def test_timezone():
    """Test timezone functionality to validate settings"""
    logger.info("=== Testing Timezone Settings ===")
    
    # Get current time in various timezones
    utc_now = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone('US/Eastern')
    et_now = utc_now.astimezone(eastern)
    local_now = datetime.datetime.now()
    
    # Log times for debugging
    logger.info(f"UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"ET time via direct conversion: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Test our get_eastern_time function
    function_et = get_eastern_time()
    logger.info(f"ET time via get_eastern_time(): {function_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Validate that both methods return the same hour
    if et_now.hour != function_et.hour:
        logger.error(f"TIMEZONE ERROR: ET hours don't match! Direct: {et_now.hour}, Function: {function_et.hour}")
    else:
        logger.info(f"Timezone validation successful: ET hour is {et_now.hour}")
    
    # Check DST status
    is_dst = et_now.dst() != datetime.timedelta(0)
    logger.info(f"Is DST active: {is_dst}")
    
    # Test market period detection
    period = get_current_market_period()
    logger.info(f"Current market period: {period}")
    
    return et_now

def test_timezone():
    """Test timezone functionality to validate settings"""
    logger.info("=== Testing Timezone Settings ===")
    
    # Get current time in various timezones
    utc_now = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone('US/Eastern')
    et_now = utc_now.astimezone(eastern)
    local_now = datetime.datetime.now()
    
    # Log times for debugging
    logger.info(f"UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"ET time via direct conversion: {et_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Test our get_eastern_time function
    function_et = get_eastern_time()
    logger.info(f"ET time via get_eastern_time(): {function_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Validate that both methods return the same hour
    if et_now.hour != function_et.hour:
        logger.error(f"TIMEZONE ERROR: ET hours don't match! Direct: {et_now.hour}, Function: {function_et.hour}")
    else:
        logger.info(f"Timezone validation successful: ET hour is {et_now.hour}")
    
    # Check DST status
    is_dst = et_now.dst() != datetime.timedelta(0)
    logger.info(f"Is DST active: {is_dst}")
    
    # Test market period detection
    period = get_current_market_period()
    logger.info(f"Current market period: {period}")
    
    return et_now

def main_loop():
    # Test timezone functionality first
    test_timezone()
    """Main scheduler loop"""
    global running
    
    # Create data directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)
    Path("data/orders").mkdir(exist_ok=True)
    Path("data/orb_data").mkdir(exist_ok=True)
    
    # Test timezone functionality first
    test_timezone()
    
    # Log initial status
    log_status()
    
    logger.info("Starting Windows-compatible ORB News Trader scheduler")
    print("Scheduler running... Press Ctrl+C to stop")
    
    try:
        # Set running flag
        running = True
        
        while running:
            try:
                # Log current status
                log_status()
                
                # Check if we should run now
                if should_run_now():
                    logger.info("Running trading bot")
                    run_with_retries()
                else:
                    logger.info("Skipping run based on schedule")
                
                # Calculate time until next check
                period = get_current_market_period()
                next_check_minutes = CONFIG["check_intervals"][period]
                
                logger.info(f"Waiting {next_check_minutes} minutes until next check")
                
                # Wait in a way that allows for keyboard interrupt
                for _ in range(next_check_minutes * 60):
                    if not running:
                        break
                    time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping scheduler")
                running = False
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait a minute before trying again
                time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping scheduler")
        running = False
    
    logger.info("Scheduler stopped")

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping scheduler")
        print("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Unhandled error in scheduler: {e}")
        raise