# timezone_utils.py
# Helper functions for timezone conversion and market time calculations

import datetime
import pytz
import logging

logger = logging.getLogger('timezone_utils')

def get_eastern_time():
    """
    Get the current time in US Eastern Time (ET), which is the timezone for US markets
    
    Returns:
        datetime: Current datetime in Eastern Time
    """
    # Get current UTC time
    utc_now = datetime.datetime.now(pytz.UTC)
    
    # Convert to Eastern Time
    eastern = pytz.timezone('US/Eastern')
    eastern_time = utc_now.astimezone(eastern)
    
    # Log for debugging
    logger.debug(f"UTC time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.debug(f"Eastern time: {eastern_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.debug(f"Is DST active: {eastern_time.dst() != datetime.timedelta(0)}")
    
    return eastern_time

def log_current_time():
    """Log the current time in various timezones for debugging"""
    # Get current time in various timezones
    now_utc = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone('US/Eastern')
    now_et = now_utc.astimezone(eastern)
    now_local = datetime.datetime.now()
    
    # Try to get the local timezone name
    try:
        local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    except:
        local_tz = "Unknown"
    
    # Log all times with detailed information
    logger.info(f"Current times - UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"Current times - ET:  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')} (DST active: {now_et.dst() != datetime.timedelta(0)})")
    logger.info(f"Current times - Local: {now_local.strftime('%Y-%m-%d %H:%M:%S')} (timezone: {local_tz})")
    
    # Get the current market period
    period_key, period_name, interval = get_current_market_period()
    logger.info(f"Current market period: {period_key} ({period_name}), interval: {interval} minutes")
    
    return now_et

def get_current_market_period():
    """
    Determine the current market time period for scheduling purposes
    
    Returns:
        tuple: (period_key, period_name, interval_minutes)
    """
    # Get current Eastern Time
    et_now = get_eastern_time()
    
    # Extract hour (0-23) in Eastern Time
    et_hour = et_now.hour
    et_minute = et_now.minute
    
    # Log the hour for debugging
    logger.debug(f"Current hour in ET: {et_hour}")
    
    # Determine the period based on time
    if 4 <= et_hour < 9 or (et_hour == 9 and et_minute < 30):
        return ("pre_market", "Pre-market", 15)
    elif (et_hour == 9 and et_minute >= 30) or (et_hour == 10 and et_minute < 30):
        return ("market_open", "Market open", 5)
    elif (et_hour == 10 and et_minute >= 30) or (et_hour == 11):
        return ("morning", "Morning session", 15)
    elif 12 <= et_hour < 14:
        return ("midday", "Midday", 30)
    elif 14 <= et_hour < 15:
        return ("afternoon", "Afternoon session", 15)
    elif 15 <= et_hour < 16:
        return ("power_hour", "Power hour", 10)
    elif 16 <= et_hour < 20:
        return ("after_hours", "After-hours", 20)
    elif 20 <= et_hour < 24:
        return ("evening", "Evening", 45)
    else:  # 0 <= et_hour < 4
        return ("overnight", "Overnight", 90)

def log_current_time():
    """Log the current time in various timezones for debugging"""
    # Get current time in various timezones
    now_utc = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone('US/Eastern')
    now_et = now_utc.astimezone(eastern)
    now_local = datetime.datetime.now()
    
    # Try to get the local timezone name
    try:
        local_tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
    except:
        local_tz = "Unknown"
    
    # Log all times with detailed information
    logger.info(f"Current times - UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"Current times - ET:  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')} (DST active: {now_et.dst() != datetime.timedelta(0)})")
    logger.info(f"Current times - Local: {now_local.strftime('%Y-%m-%d %H:%M:%S')} (timezone: {local_tz})")
    
    # Get the current market period
    period_key, period_name, interval = get_current_market_period()
    logger.info(f"Current market period: {period_key} ({period_name}), interval: {interval} minutes")
    
    return now_et

if __name__ == "__main__":
    # Configure logging when run directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('timezone_utils')
    
    # Test and print timezone information
    logger.info("=== Testing timezone utilities ===")
    et_time = log_current_time()
    print(f"ET Time: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Is DST active: {et_time.dst() != datetime.timedelta(0)}")
    print(f"Current ET hour: {et_time.hour}")
    
    # Test the market period function
    period_key, period_name, interval = get_current_market_period()
    print(f"Current market period: {period_key} ({period_name})")
    print(f"Recommended polling interval: {interval} minutes")