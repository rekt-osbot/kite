#!/usr/bin/env python
"""
NSE Holidays Module

This module provides functionality to check market holidays for the National Stock Exchange (NSE) of India.
It maintains a list of holidays for the current year and provides utilities to determine market operating status.
"""
import logging
import datetime
from datetime import datetime as dt, timedelta
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define NSE market hours
MARKET_OPEN_TIME = datetime.time(9, 15)  # 9:15 AM
MARKET_CLOSE_TIME = datetime.time(15, 30)  # 3:30 PM
MARKET_PRE_OPEN_TIME = datetime.time(9, 0)  # 9:00 AM

# Define regular weekly off days (0 = Monday, 6 = Sunday)
WEEKLY_OFFS = [5, 6]  # Saturday and Sunday

# Define 2025 NSE holidays (this should be updated annually)
# Format: 'YYYY-MM-DD': 'Holiday Name'
NSE_HOLIDAYS_2025 = {
    '2025-01-01': 'New Year',
    '2025-01-26': 'Republic Day',
    '2025-03-25': 'Holi',
    '2025-04-14': 'Dr. Ambedkar Jayanti',
    '2025-04-18': 'Good Friday',
    '2025-05-01': 'Maharashtra Day',
    '2025-06-29': 'Bakri Id',
    '2025-08-15': 'Independence Day',
    '2025-09-02': 'Ganesh Chaturthi',
    '2025-10-02': 'Gandhi Jayanti',
    '2025-10-24': 'Dussehra',
    '2025-11-12': 'Diwali',
    '2025-11-25': 'Guru Nanak Jayanti', 
    '2025-12-25': 'Christmas'
}

def is_market_holiday(date):
    """
    Check if a given date is a market holiday.
    
    Args:
        date (datetime.date or datetime.datetime): The date to check
        
    Returns:
        bool: True if the date is a holiday, False otherwise
    """
    # Use IST timezone for consistency
    ist = pytz.timezone('Asia/Kolkata')
    
    # If we got a datetime with timezone, use date() to get just the date
    if isinstance(date, datetime.datetime):
        # Convert to IST if it has a timezone
        if date.tzinfo is not None:
            date = date.astimezone(ist).date()
        else:
            # If no timezone, assume it's already in IST
            date = date.date()
    
    # Ensure we're working with a proper date object
    if not isinstance(date, datetime.date):
        logger.warning(f"Unexpected date type: {type(date)}, attempting conversion")
        try:
            date = datetime.date(date.year, date.month, date.day)
        except Exception as e:
            logger.error(f"Failed to convert date: {e}")
            return False
    
    # Check if it's a weekend
    if date.weekday() in WEEKLY_OFFS:
        return True
    
    # Check if it's in the holiday list
    # First check if the date is in the current year's format
    curr_year = datetime.datetime.now(ist).year
    date_str = date.strftime('%Y-%m-%d')
    
    # Direct lookup in holiday list
    if date_str in NSE_HOLIDAYS_2025:
        return True
    
    # If year is different, try checking with the current year
    if date.year != 2025:
        alt_date_str = f"2025-{date.month:02d}-{date.day:02d}"
        if alt_date_str in NSE_HOLIDAYS_2025:
            logger.warning(f"Date {date_str} matched holiday after year adjustment to {alt_date_str}")
            return True
    
    # Not a holiday
    return False

def get_holiday_name(date):
    """
    Get the name of the holiday for a given date.
    
    Args:
        date (datetime.date): The date to check
        
    Returns:
        str: The name of the holiday, or None if it's not a holiday
    """
    # Convert to date object if datetime was provided
    if isinstance(date, datetime.datetime):
        date = date.date()
    
    # Check if it's a weekend
    if date.weekday() in WEEKLY_OFFS:
        return "Weekend"
    
    # Check if it's in the holiday list
    date_str = date.strftime('%Y-%m-%d')
    return NSE_HOLIDAYS_2025.get(date_str)

def get_next_trading_day(date):
    """
    Get the next trading day after the given date.
    
    Args:
        date (datetime.date): The starting date
        
    Returns:
        datetime.date: The next trading day
    """
    # Convert to date object if datetime was provided
    if isinstance(date, datetime.datetime):
        date = date.date()
    
    # Start with the next day
    next_day = date + timedelta(days=1)
    
    # Keep incrementing until we find a trading day
    while is_market_holiday(next_day):
        next_day += timedelta(days=1)
    
    return next_day

def is_market_open(timestamp=None):
    """
    Check if the market is currently open based on the current time or given timestamp.
    
    Args:
        timestamp (datetime.datetime, optional): The timestamp to check. If None, the current time is used.
        
    Returns:
        bool: True if the market is open, False otherwise
    """
    # Get IST timezone
    ist = pytz.timezone('Asia/Kolkata')
    
    # Use current time if no timestamp is provided
    if timestamp is None:
        timestamp = dt.now(ist)
    elif timestamp.tzinfo is None:
        # If the timestamp has no timezone, assume it's IST
        timestamp = ist.localize(timestamp)
    
    # Check if it's a holiday
    if is_market_holiday(timestamp.date()):
        return False
    
    # Check market hours
    current_time = timestamp.time()
    return MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME

def get_market_status():
    """
    Get the current market status with detailed information.
    
    Returns:
        dict: A dictionary with market status information
    """
    # Get IST timezone
    ist = pytz.timezone('Asia/Kolkata')
    now = dt.now(ist)
    today = now.date()
    current_time = now.time()
    
    # Check if today is a holiday
    holiday = is_market_holiday(today)
    holiday_name = get_holiday_name(today) if holiday else None
    
    # Determine the next trading day
    next_trading_day = today if not holiday and current_time < MARKET_CLOSE_TIME else get_next_trading_day(today)
    
    # Calculate next market open timestamp
    if holiday or current_time > MARKET_CLOSE_TIME:
        # Market is closed for the day, next opening is on the next trading day
        next_open_timestamp = dt.combine(next_trading_day, MARKET_OPEN_TIME)
        next_open_timestamp = ist.localize(next_open_timestamp)
    elif current_time < MARKET_OPEN_TIME:
        # Market hasn't opened yet today
        next_open_timestamp = dt.combine(today, MARKET_OPEN_TIME)
        next_open_timestamp = ist.localize(next_open_timestamp)
    else:
        # Market is currently open, so the next open is tomorrow or after weekend/holiday
        next_open_timestamp = dt.combine(next_trading_day, MARKET_OPEN_TIME)
        next_open_timestamp = ist.localize(next_open_timestamp)
    
    # Determine current status
    if holiday:
        status = 'CLOSED_HOLIDAY'
        status_message = f'Market closed for holiday: {holiday_name}'
    elif current_time < MARKET_PRE_OPEN_TIME:
        status = 'CLOSED_PRE_MARKET'
        status_message = 'Market closed - Pre-market session starts at 9:00 AM'
    elif current_time < MARKET_OPEN_TIME:
        status = 'PRE_OPEN'
        status_message = 'Pre-market session - Regular trading starts at 9:15 AM'
    elif current_time <= MARKET_CLOSE_TIME:
        status = 'OPEN'
        status_message = 'Market open - Regular trading hours'
    else:
        status = 'CLOSED_POST_MARKET'
        status_message = 'Market closed for the day'
    
    # Create status dictionary
    return {
        'status': status,
        'message': status_message,
        'current_time': now,
        'is_open': MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME and not holiday,
        'is_holiday': holiday,
        'holiday_name': holiday_name,
        'next_trading_day': next_trading_day,
        'next_market_open': next_open_timestamp
    }

def fetch_nse_holidays():
    """
    Fetch NSE holidays from our predefined list.
    This function maintains compatibility with existing code that expects this function.
    
    Returns:
        list: A list of dictionaries containing holiday dates and descriptions
    """
    holidays = []
    current_year = dt.now().year
    
    # Convert our dictionary to the expected format
    for date_str, description in NSE_HOLIDAYS_2025.items():
        # Parse the year from the date string
        holiday_year = int(date_str.split('-')[0])
        
        # Only include holidays for the current year or future years
        # This is to maintain compatibility with the original function's behavior
        if holiday_year >= current_year:
            holidays.append({
                'date': date_str,
                'description': description
            })
    
    # Sort holidays by date
    holidays = sorted(holidays, key=lambda x: x['date'])
    
    logger.info(f"Fetched {len(holidays)} NSE holidays for {current_year} and beyond")
    return holidays

if __name__ == "__main__":
    # Test the module functions
    logger.info("Testing NSE Holidays module...")
    
    # Check current market status
    status = get_market_status()
    logger.info(f"Current market status: {status['status']}")
    logger.info(f"Status message: {status['message']}")
    logger.info(f"Is market open: {status['is_open']}")
    logger.info(f"Next trading day: {status['next_trading_day']}")
    logger.info(f"Next market open: {status['next_market_open']}")
    
    # Check some known holidays
    republic_day = dt(2025, 1, 26).date()
    logger.info(f"Is Republic Day (2025-01-26) a holiday? {is_market_holiday(republic_day)}")
    logger.info(f"Holiday name: {get_holiday_name(republic_day)}")
    
    # Check next trading day after a holiday
    next_day = get_next_trading_day(republic_day)
    logger.info(f"Next trading day after Republic Day: {next_day}")
    
    logger.info("NSE Holidays module test complete.") 