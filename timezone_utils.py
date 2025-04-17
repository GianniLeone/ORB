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
    
    return eastern_time

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
    
    # Define market periods with their time ranges and intervals
    market_periods = [
        {
            "key": "4am-9am",
            "name": "Pre-market",
            "start_hour": 4,
            "end_hour": 9,
            "interval_minutes": 15
        },
        {
            "key": "9am-12pm",
            "name": "Market open",
            "start_hour": 9,
            "end_hour": 12,
            "interval_minutes": 5
        },
        {
            "key": "12pm-3pm",
            "name": "Midday",
            "start_hour": 12,
            "end_hour": 15,
            "interval_minutes": 30
        },
        {
            "key": "3pm-4pm",
            "name": "Power hour",
            "start_hour": 15,
            "end_hour": 16,
            "interval_minutes": 10
        },
        {
            "key": "4pm-6pm",
            "name": "After-hours",
            "start_hour": 16,
            "end_hour": 18,
            "interval_minutes": 20
        },
        {
            "key": "6pm-12am",
            "name": "Evening",
            "start_hour": 18,
            "end_hour": 24,  # midnight
            "interval_minutes": 45
        },
        {
            "key": "12am-4am",
            "name": "Overnight",
            "start_hour": 0,  # midnight
            "end_hour": 4,
            "interval_minutes": 90
        }
    ]
    
    # Find the current period
    for period in market_periods:
        if period["start_hour"] <= et_hour < period["end_hour"]:
            logger.debug(f"Current ET hour: {et_hour}, matching period: {period['key']}")
            return (
                period["key"],
                period["name"], 
                period["interval_minutes"]
            )
    
    # This should never happen since the periods cover all 24 hours
    logger.error(f"Could not determine market period for hour {et_hour}")
    # Default to the overnight period
    return ("12am-4am", "Overnight", 90)

def log_current_time():
    """Log the current time in various timezones for debugging"""
    now_utc = datetime.datetime.now(pytz.UTC)
    now_et = now_utc.astimezone(pytz.timezone('US/Eastern'))
    now_local = datetime.datetime.now()
    
    logger.info(f"Current times - UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"Current times - ET:  {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"Current times - Local: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    et_time = log_current_time()
    print(f"ET Time: {et_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")