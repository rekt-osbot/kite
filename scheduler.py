import os
import time
import logging
import requests
import threading
import pytz
from datetime import datetime, timedelta
from nse_holidays import is_market_holiday, get_next_trading_day
from token_manager import token_manager

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

def is_market_open():
    """
    Check if the market is currently open.
    Returns True if it's a weekday (Monday-Friday), not a holiday, and time is between 9:00 AM to 3:30 PM IST.
    """
    # IMPORTANT: Always use IST timezone for market operations
    now = datetime.now(IST)
    logger.info(f"Current date/time (IST): {now}")
    
    # Check if it's a weekday (0 is Monday, 6 is Sunday)
    weekday = now.weekday()
    if weekday > 4:  # Saturday or Sunday
        logger.info(f"Market closed: Weekend (weekday {weekday})")
        return False
    
    # Force date to have the correct timezone
    date_to_check = now.date()
    
    # Check if it's a holiday
    if is_market_holiday(date_to_check):
        logger.info(f"Market closed: Holiday on {date_to_check}")
        return False
    
    # Create datetime objects for market open (9:00 AM) and close (3:30 PM)
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if current time is within market hours
    if market_open <= now <= market_close:
        logger.info(f"Market open: Within trading hours ({now.strftime('%H:%M')})")
        return True
    else:
        logger.info(f"Market closed: Outside trading hours ({now.strftime('%H:%M')})")
        return False

def calculate_next_market_open():
    """Calculate the next time the market will open"""
    now = datetime.now(IST)
    
    # Get the next trading day
    next_trading_day = get_next_trading_day(now.date())
    
    # If today is a trading day and it's before market open
    if not is_market_holiday(now) and now.weekday() < 5 and now.hour < 9:
        # Market opens today at 9:00 AM
        return now.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # If we have a valid next trading day
    if next_trading_day:
        # Market opens at 9:00 AM on the next trading day
        next_open = datetime.combine(next_trading_day, 
                                   datetime.min.time()).replace(
                                      hour=9, minute=0, second=0, microsecond=0, tzinfo=IST)
        return next_open
    
    # Fallback - return None if we can't determine
    logger.warning("Could not determine next market open time")
    return None

def check_auth_and_token_status():
    """
    Check token status and trigger appropriate actions.
    Returns True if authentication is valid.
    """
    try:
        # Check if token is valid for trading
        is_valid = token_manager.is_trading_enabled()
        
        if not is_valid:
            logger.warning("Trading disabled: Token has expired or is invalid")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Error checking token status: {e}")
        return False

def auth_checker_thread():
    """Thread to periodically check authentication status"""
    logger.info("Starting authentication checker thread")
    
    # Wait 60 seconds after startup to allow server to initialize
    time.sleep(60)
    
    while True:
        try:
            check_auth_and_token_status()
        except Exception as e:
            logger.error(f"Error in auth checker thread: {e}")
        
        # Check every 15 minutes
        time.sleep(15 * 60)

def start_scheduler():
    """Start scheduler background process"""
    # Start authentication checker thread
    t = threading.Thread(target=auth_checker_thread, daemon=True)
    t.start()
    logger.info("Scheduler started") 