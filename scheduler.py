import os
import time
import logging
import requests
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='scheduler.log'
)
logger = logging.getLogger(__name__)

def trigger_login_notification():
    """Send a notification that login is required"""
    app_url = os.getenv("APP_URL", "")
    if not app_url:
        logger.error("APP_URL not set in environment variables")
        return
    
    login_url = f"{app_url}/auth/refresh"
    
    logger.info(f"Token expired. Login required at: {login_url}")
    
    # You could add notification via email, Telegram, etc.
    # For example, using a free service like ntfy.sh:
    ntfy_topic = os.getenv("NTFY_TOPIC", "")
    if ntfy_topic:
        try:
            requests.post(
                f"https://ntfy.sh/{ntfy_topic}",
                data=f"Zerodha token expired! Login required: {login_url}".encode("utf-8"),
                headers={
                    "Title": "Zerodha Login Required",
                    "Priority": "urgent",
                    "Tags": "warning"
                }
            )
            logger.info(f"Notification sent to ntfy.sh/{ntfy_topic}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

def check_auth_status():
    """Check if the Kite API is authenticated"""
    app_url = os.getenv("APP_URL", "")
    if not app_url:
        logger.error("APP_URL not set in environment variables")
        return False
    
    status_url = f"{app_url}/auth/status"
    
    try:
        response = requests.get(status_url)
        data = response.json()
        
        if data.get("authenticated", False):
            logger.info(f"Authentication valid. User: {data.get('user')}")
            return True
        else:
            logger.warning("Authentication invalid or expired")
            trigger_login_notification()
            return False
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return False

def auth_checker_thread():
    """Thread that periodically checks authentication status"""
    # Check after a delay on startup (give the server time to start)
    time.sleep(60)
    check_auth_status()
    
    # Schedule checks - Zerodha tokens expire at 6 AM IST
    # So we'll check a few times during the day
    check_interval = 4 * 60 * 60  # 4 hours in seconds
    
    while True:
        time.sleep(check_interval)
        check_auth_status()

def start_scheduler():
    """Start the scheduler thread"""
    thread = threading.Thread(target=auth_checker_thread, daemon=True)
    thread.start()
    logger.info("Auth checker scheduler started") 