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
    Returns True if it's a weekday (Monday-Friday), not a holiday, and time is between 9:00 AM to 3:30 PM IST.
    """
    # Import here to avoid circular imports
    from nse_holidays import is_market_holiday
    
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
    # Import here to avoid circular imports
    from nse_holidays import get_next_trading_day, is_market_holiday
    
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

def wait_for_market_open():
    """Wait until the market opens by calculating sleep time"""
    last_notification_time = None
    
    while True:
        if is_market_open():
            logger.info("Market is now open. Starting application...")
            
            # Send notification that market is now open
            try:
                from telegram_notifier import TelegramNotifier
                telegram = TelegramNotifier()
                now = datetime.now(IST)
                
                message = f"🟢 <b>Market Now Open</b>\n\n" \
                        f"The trading bot has started in full mode as the market is now open.\n" \
                        f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n\n" \
                        f"Trading operations have resumed automatically."
                
                telegram.send_message(message)
                logger.info("Sent market open notification via Telegram")
            except Exception as e:
                logger.error(f"Failed to send market open notification: {e}")
                
            break
        
        next_open = calculate_next_market_open()
        current_time = datetime.now(IST)
        
        if next_open:
            wait_seconds = (next_open - current_time).total_seconds()
            
            if wait_seconds > 0:
                # Send periodic updates (but not too frequently - max once per 6 hours)
                should_notify = False
                
                if last_notification_time is None:
                    should_notify = True
                elif (current_time - last_notification_time).total_seconds() > 6 * 3600:  # 6 hours
                    should_notify = True
                
                if should_notify:
                    try:
                        from nse_holidays import is_market_holiday, fetch_nse_holidays
                        from telegram_notifier import TelegramNotifier
                        
                        # Get current reason for market closure
                        closure_reason = ""
                        if current_time.weekday() > 4:
                            closure_reason = "weekend"
                        elif is_market_holiday(current_time):
                            holidays = fetch_nse_holidays()
                            date_str = current_time.strftime('%Y-%m-%d')
                            for holiday in holidays:
                                if holiday.get('date') == date_str:
                                    closure_reason = holiday.get('description', 'holiday')
                                    break
                        else:
                            closure_reason = "outside trading hours"
                        
                        # Send notification
                        telegram = TelegramNotifier()
                        hours_to_wait = round(wait_seconds / 3600, 1)
                        
                        message = f"⏳ <b>Waiting for Market to Open</b>\n\n" \
                                f"The trading bot is waiting for the market to open ({closure_reason}).\n" \
                                f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                                f"Next market open: {next_open.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                                f"Waiting for approximately {hours_to_wait} hours\n\n" \
                                f"The bot will automatically start when the market opens."
                        
                        telegram.send_message(message)
                        last_notification_time = current_time
                        logger.info(f"Sent waiting notification via Telegram: Waiting {hours_to_wait} hours for market to open")
                    except Exception as e:
                        logger.error(f"Failed to send waiting notification: {e}")
                
                logger.info(f"Market is closed. Next open at {next_open.strftime('%Y-%m-%d %H:%M:%S')} - sleeping for {wait_seconds/3600:.1f} hours")
                
                # Sleep in smaller increments to be more responsive to interrupts
                sleep_interval = min(wait_seconds, 15 * 60)  # 15 minutes max
                time.sleep(sleep_interval)
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
    
    # Skip database initialization completely - we'll use file-based storage instead
    logger.info("Using file-based storage instead of database to reduce costs")
    
    # Set environment variables
    if bypass_market_hours or is_market_open():
        # Market is open or bypass is enabled
        logger.info("Market is open or bypass enabled. Starting full app.")
        os.environ["MARKET_CLOSED"] = "False"
    else:
        # Market is closed
        logger.info("Market is closed. Starting lightweight version of app.")
        os.environ["MARKET_CLOSED"] = "True"
        
        # Send notification if market is closed due to a holiday
        try:
            # Import here to avoid circular imports
            from nse_holidays import is_market_holiday, fetch_nse_holidays
            
            if is_market_holiday(datetime.now(IST)):
                # Only import what we need for notification
                try:
                    from telegram_notifier import TelegramNotifier
                    
                    # Get holiday description
                    holidays = fetch_nse_holidays()
                    now = datetime.now(IST)
                    date_str = now.strftime('%Y-%m-%d')
                    holiday_desc = "Holiday"
                    
                    for holiday in holidays:
                        if holiday.get('date') == date_str:
                            holiday_desc = holiday.get('description', 'Holiday')
                            break
                    
                    # Calculate next market open time
                    next_open = calculate_next_market_open()
                    next_open_str = next_open.strftime('%Y-%m-%d %H:%M:%S IST') if next_open else "Unknown"
                    
                    # Initialize and send notification
                    telegram = TelegramNotifier()
                    message = f"🔴 <b>Market Closed: {holiday_desc}</b>\n\n" \
                            f"The trading bot has been started in lightweight mode due to a market holiday.\n" \
                            f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                            f"Next market open: {next_open_str}\n\n" \
                            f"The bot will automatically switch to full mode when the market reopens."
                    
                    telegram.send_message(message)
                    logger.info(f"Sent market holiday notification via Telegram: Market closed for {holiday_desc}")
                except Exception as e:
                    logger.error(f"Failed to send market holiday notification: {e}")
        except Exception as e:
            logger.error(f"Error checking for market holiday: {e}")
    
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