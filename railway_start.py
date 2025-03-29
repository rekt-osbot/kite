#!/usr/bin/env python
"""
Railway starter script that handles the market hours check
and starts the appropriate application.
"""
import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timedelta
import pytz

# Configure logging
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
    Returns True if it's a weekday (Monday-Friday) and time is between 9:00 AM to 3:30 PM IST.
    """
    # Get current time in IST
    now = datetime.now(IST)
    # Check if it's a weekday (0 is Monday, 6 is Sunday)
    if now.weekday() > 4:  # Saturday or Sunday
        logger.info("Market closed: Weekend")
        return False
    
    # Create datetime objects for market open (9:00 AM) and close (3:30 PM)
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
    next_market_open = None
    
    # If it's a weekend, find the next Monday
    if now.weekday() > 4:  # Saturday or Sunday
        days_to_monday = (7 - now.weekday()) % 7
        if days_to_monday == 0:  # If it's already Monday
            days_to_monday = 7
        next_market_open = (now + timedelta(days=days_to_monday)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
    # If it's before market open on a weekday
    elif now.hour < 9:
        next_market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    # If it's after market close on a weekday (not Friday)
    elif now.weekday() < 4 and (now.hour > 15 or (now.hour == 15 and now.minute >= 30)):
        next_market_open = (now + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
    # If it's after market close on Friday
    elif now.weekday() == 4 and (now.hour > 15 or (now.hour == 15 and now.minute >= 30)):
        next_market_open = (now + timedelta(days=3)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
    
    return next_market_open

def wait_for_market_open():
    """Wait until the market opens by calculating sleep time"""
    while True:
        if is_market_open():
            logger.info("Market is now open. Starting application...")
            break
        
        next_open = calculate_next_market_open()
        if next_open:
            wait_seconds = (next_open - datetime.now(IST)).total_seconds()
            if wait_seconds > 0:
                logger.info(f"Market is closed. Next open at {next_open.strftime('%Y-%m-%d %H:%M:%S')} - sleeping for {wait_seconds/3600:.1f} hours")
                time.sleep(wait_seconds)
            else:
                # If next_open is in the past (e.g. calculation error), sleep shortly
                logger.info("Calculation error or market should be open already. Checking again in 5 minutes.")
                time.sleep(300)
        else:
            # Fallback - sleep for 15 minutes
            logger.info("Could not determine next market open. Checking again in 15 minutes.")
            time.sleep(900)

def main():
    """Main function to start the application with market hours checking"""
    # Check if market hours bypass is enabled
    bypass_market_hours = os.getenv("BYPASS_MARKET_HOURS", "False").lower() == "true"
    
    # First run the railway setup to initialize database
    logger.info("Running railway_setup.py...")
    subprocess.run([sys.executable, "railway_setup.py"])
    
    if not bypass_market_hours:
        # Only run the app during market hours
        if not is_market_open():
            logger.info("Market is closed. Starting lightweight version of app.")
            # Set environment variable to tell the app to run in market closed mode
            os.environ["MARKET_CLOSED"] = "True"
        else:
            logger.info("Market is open. Starting full app.")
            os.environ["MARKET_CLOSED"] = "False"
    else:
        logger.info("Market hours check bypassed. Starting full app regardless of market status.")
        os.environ["MARKET_CLOSED"] = "False"
    
    # Start the Flask application using gunicorn for production
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting chartink_webhook.py with gunicorn on port {port}...")
    
    # Import the app without running it
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Use gunicorn for production
    try:
        from gunicorn.app.wsgiapp import WSGIApplication
        
        class GunicornApp(WSGIApplication):
            def __init__(self, app_uri, options=None):
                self.options = options or {}
                self.app_uri = app_uri
                super().__init__()
                
            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)
        
        options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 1,  # Using just 1 worker to save resources
            'timeout': 120,
            'accesslog': '-',  # Log to stdout
            'errorlog': '-',   # Log errors to stdout
            'loglevel': 'info'
        }
        
        # Run the gunicorn app
        GunicornApp('chartink_webhook:app', options).run()
    except ImportError:
        # Fallback to direct Flask app execution if gunicorn is not available
        logger.warning("Gunicorn not available, falling back to Flask development server")
        subprocess.run([sys.executable, "chartink_webhook.py"])

if __name__ == "__main__":
    main() 