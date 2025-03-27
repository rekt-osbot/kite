import os
import time
import logging
import requests
import threading
from datetime import datetime, timedelta

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        # Try to use the APP_URL environment variable, fall back to localhost
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