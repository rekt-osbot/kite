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
import gc  # Add garbage collection for memory optimization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Memory optimization settings
MEMORY_CHECK_INTERVAL = 30 * 60  # Check memory usage every 30 minutes
FORCED_GC_INTERVAL = 2 * 60 * 60  # Force garbage collection every 2 hours
last_memory_check = 0
last_gc_time = 0

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

def optimize_memory():
    """
    Perform memory optimization tasks to reduce application footprint
    """
    global last_memory_check, last_gc_time
    current_time = time.time()
    
    # Check memory usage periodically
    if current_time - last_memory_check > MEMORY_CHECK_INTERVAL:
        last_memory_check = current_time
        
        try:
            # Force garbage collection periodically
            if current_time - last_gc_time > FORCED_GC_INTERVAL:
                before_count = len(gc.get_objects())
                gc.collect()
                after_count = len(gc.get_objects())
                last_gc_time = current_time
                logger.info(f"Memory optimization: Garbage collection freed {before_count - after_count} objects")
        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")

def wait_for_market_open():
    """Wait until the market opens by calculating sleep time - with optimized resource usage"""
    last_notification_time = None
    
    while True:
        # Check if market is open now
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
        
        # Optimize memory while waiting
        optimize_memory()
        
        # Calculate when the market will next open
        next_open = calculate_next_market_open()
        current_time = datetime.now(IST)
        
        if next_open:
            wait_seconds = (next_open - current_time).total_seconds()
            
            if wait_seconds > 0:
                # Determine optimal sleep strategy based on wait time
                is_long_wait = wait_seconds > 3600  # More than 1 hour
                
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
                        
                        # Clean up imported modules to save memory
                        if 'telegram_notifier' in sys.modules:
                            del sys.modules['telegram_notifier']
                        if 'nse_holidays' in sys.modules:
                            del sys.modules['nse_holidays']
                        gc.collect()
                    except Exception as e:
                        logger.error(f"Failed to send waiting notification: {e}")
                
                logger.info(f"Market is closed. Next open at {next_open.strftime('%Y-%m-%d %H:%M:%S')} - sleeping for {wait_seconds/3600:.1f} hours")
                
                # Adaptive sleep strategy
                if is_long_wait:
                    # For long waits, use longer sleep intervals
                    # Calculate optimal sleep interval based on time to market open
                    # Cap at 1 hour maximum sleep for responsiveness
                    sleep_interval = min(3600, max(300, wait_seconds / 10))
                else:
                    # For shorter waits, use more frequent checks (15 minutes max)
                    sleep_interval = min(wait_seconds, 15 * 60)
                
                logger.info(f"Using sleep interval of {sleep_interval/60:.1f} minutes")
                time.sleep(sleep_interval)
            else:
                # If next_open is in the past (e.g. calculation error), sleep shortly
                logger.info("Calculation error or market should be open already. Checking again in 5 minutes.")
                time.sleep(300)
        else:
            # Fallback - sleep for 15 minutes
            logger.info("Could not determine next market open. Checking again in 15 minutes.")
            time.sleep(900)

def launch_minimal_app():
    """Launch a minimal version of the app with reduced resources when market is closed"""
    logger.info("Launching minimal version of the app during market closure")
    
    # Set environment variables to indicate running in minimal mode
    os.environ["MINIMAL_MODE"] = "True"
    os.environ["MARKET_CLOSED"] = "True"
    
    # Import necessary modules
    from chartink_webhook import create_market_closed_app
    
    # Create minimal Flask app
    minimal_app = create_market_closed_app()
    
    # Configure minimal gunicorn settings to reduce resource usage
    minimal_workers = 1
    minimal_threads = 2
    
    port = int(os.getenv("PORT", 5000))
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': minimal_workers,
        'threads': minimal_threads,
        'timeout': 30,  # Reduced timeout for minimal mode
        'accesslog': '-',
        'errorlog': '-',
        'loglevel': 'warning',  # Reduce logging in minimal mode
        'worker_class': 'sync',  # Use sync worker for minimal resources
        'max_requests': 1000,    # Restart workers periodically to prevent memory bloat
        'max_requests_jitter': 500
    }
    
    # Start gunicorn with minimal app
    try:
        from gunicorn.app.base import BaseApplication
        
        class MinimalGunicornApp(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()
                
            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)
                        
            def load(self):
                return self.application
        
        MinimalGunicornApp(minimal_app, options).run()
    except ImportError:
        # Fallback to direct Flask app execution if gunicorn is not available
        logger.warning("Gunicorn not available, falling back to Flask development server")
        minimal_app.run(host="0.0.0.0", port=port, debug=False)

def main():
    """Main function to start the application with market hours checking and resource optimization"""
    # Check if market hours bypass is enabled
    bypass_market_hours = os.getenv("BYPASS_MARKET_HOURS", "False").lower() == "true"
    
    # Skip database initialization completely - we'll use file-based storage instead
    logger.info("Using file-based storage instead of database to reduce costs")
    
    # Check if we should run in minimal mode (during market closed hours)
    if not bypass_market_hours and not is_market_open():
        logger.info("Market is closed. Entering standby mode with minimal resource usage.")
        
        # Send market closure notification if it's due to a holiday
        try:
            now = datetime.now(IST)
            from nse_holidays import is_market_holiday, fetch_nse_holidays
            
            if is_market_holiday(now.date()):
                # Only import what we need for notification
                try:
                    from telegram_notifier import TelegramNotifier
                    
                    # Get holiday description
                    holidays = fetch_nse_holidays()
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
                            f"The trading bot has entered minimal resource mode due to a market holiday.\n" \
                            f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                            f"Next market open: {next_open_str}\n\n" \
                            f"The bot will automatically switch to full mode when the market reopens."
                    
                    telegram.send_message(message)
                    logger.info(f"Sent market holiday notification via Telegram: Market closed for {holiday_desc}")
                    
                    # Clean up imported modules
                    if 'telegram_notifier' in sys.modules:
                        del sys.modules['telegram_notifier']
                    gc.collect()
                except Exception as e:
                    logger.error(f"Failed to send market holiday notification: {e}")
            
            # Clean up imported modules
            if 'nse_holidays' in sys.modules:
                del sys.modules['nse_holidays']
            gc.collect()
        except Exception as e:
            logger.error(f"Error checking for market holiday: {e}")
        
        # Start minimal web service to respond to health checks
        launch_minimal_app()
        
        # Wait until market opens (this is a blocking call)
        wait_for_market_open()
        
        # Market is now open - restart the script to use full resources
        logger.info("Market is now open - restarting script to start full application")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return
    
    # Market is open or bypass is enabled - continue with full app
    logger.info("Market is open or bypass enabled. Starting full app.")
    os.environ["MARKET_CLOSED"] = "False"
    os.environ["MINIMAL_MODE"] = "False"
    
    # If running directly, initialize token status page
    try:
        from token_status import register_token_endpoints
        import importlib.util
        
        # Check if chartink_webhook module has been imported
        if importlib.util.find_spec("chartink_webhook") is not None:
            import chartink_webhook
            # If the app attribute exists, register token endpoints
            if hasattr(chartink_webhook, 'app'):
                chartink_webhook.app = register_token_endpoints(chartink_webhook.app)
                logger.info("Registered token status endpoints with main application")
    except Exception as e:
        logger.error(f"Error registering token status endpoints: {e}")
    
    # Start the Flask application using gunicorn for production
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting chartink_webhook.py with gunicorn on port {port}...")
    
    # Import the app without running it
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Use gunicorn for production with optimized settings
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
        
        # Optimize gunicorn settings for Railway
        options = {
            'bind': f'0.0.0.0:{port}',
            'workers': 1,  # Use 1 worker to save resources
            'threads': 4,  # Use threads for better memory usage
            'timeout': 120,
            'accesslog': '-',  # Log to stdout
            'errorlog': '-',   # Log errors to stdout
            'loglevel': 'info',
            'worker_class': 'gthread',  # Use gthread for better memory usage
            'max_requests': 1000,       # Restart workers after handling 1000 requests to prevent memory bloat
            'max_requests_jitter': 500  # Add jitter to prevent all workers restarting at once
        }
        
        # Run the gunicorn app
        GunicornApp('chartink_webhook:app', options).run()
    except ImportError:
        # Fallback to direct Flask app execution if gunicorn is not available
        logger.warning("Gunicorn not available, falling back to Flask development server")
        subprocess.run([sys.executable, "chartink_webhook.py"])

if __name__ == "__main__":
    main() 