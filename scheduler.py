import os
import time
import logging
import requests
import threading
import pytz
from datetime import datetime, timedelta
from nse_holidays import is_market_holiday, get_next_trading_day

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
    now = datetime.now(IST)
    # Check if it's a weekday (0 is Monday, 6 is Sunday)
    if now.weekday() > 4:  # Saturday or Sunday
        logger.info("Market closed: Weekend")
        return False
    
    # Check if it's a holiday
    if is_market_holiday(now):
        logger.info("Market closed: Holiday")
        return False
    
    # Create datetime objects for market open (9:00 AM) and close (3:30 PM)
    # Assuming IST timezone is correctly set on the server
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if current time is within market hours
    if market_open <= now <= market_close:
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

def trigger_login_notification():
    """Trigger notification when login is required"""
    app_url = os.getenv("APP_URL", "")
    login_url = f"{app_url}/auth/refresh" if app_url else "/auth/refresh"
    
    logger.info(f"Login notification triggered: Token has expired. Login at {login_url}")
    
    # Try Telegram notification first
    try:
        from telegram_notifier import TelegramNotifier
        telegram = TelegramNotifier()
        telegram.notify_auth_status(False, "Authentication required")
        logger.info("Sent login notification via Telegram")
        return
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
    
    # Fallback to ntfy.sh
    try:
        ntfy_topic = os.getenv("NTFY_TOPIC", "kitelogin")
        requests.post(
            f"https://ntfy.sh/{ntfy_topic}",
            data=f"Zerodha token has expired. Login required at {login_url}",
            headers={"Title": "Zerodha Login Required"}
        )
        logger.info(f"Sent login notification via ntfy.sh/{ntfy_topic}")
    except Exception as e:
        logger.error(f"Failed to send ntfy.sh notification: {e}")

# Track the last notification time to avoid spamming
last_notification_time = None
last_check_time = None
last_status = None

def check_auth_status():
    """Check if authentication status is valid"""
    global last_notification_time, last_check_time, last_status
    
    # Don't check more than once every 5 minutes
    current_time = datetime.now()
    if last_check_time and (current_time - last_check_time < timedelta(minutes=5)):
        return last_status
    
    try:
        # Use file storage directly if available (when running in the same process)
        try:
            from file_storage import storage
            is_authenticated = storage.get_token() is not None
        except ImportError:
            # Fallback to API check if file storage isn't available
            # (when running in a separate process or container)
            app_url = os.getenv("APP_URL", "http://localhost:5000")
            response = requests.get(f"{app_url}/auth/status", timeout=10)
            data = response.json()
            is_authenticated = data.get('authenticated', False)
        
        # Update the last check time and status
        last_check_time = current_time
        last_status = is_authenticated
        
        # If not authenticated and we haven't notified in the last hour, send notification
        if not is_authenticated:
            if not last_notification_time or (current_time - last_notification_time > timedelta(hours=1)):
                trigger_login_notification()
                last_notification_time = current_time
                
        return is_authenticated
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return False

def auth_checker_thread():
    """Thread to periodically check authentication status"""
    logger.info("Starting authentication checker thread")
    
    # Wait 60 seconds after startup to allow server to initialize
    time.sleep(60)
    
    while True:
        try:
            check_auth_status()
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