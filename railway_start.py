#!/usr/bin/env python
"""
Railway starter script that handles the market hours check
and starts the appropriate application.
"""
import os
import sys
import time
import subprocess
import threading
from datetime import datetime, timedelta
import pytz
import gc  # Add garbage collection for memory optimization

# Import our centralized logger
from logger import get_logger

# Get logger for this module
logger = get_logger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Memory optimization settings
MEMORY_CHECK_INTERVAL = 30 * 60  # Check memory usage every 30 minutes
FORCED_GC_INTERVAL = 2 * 60 * 60  # Force garbage collection every 2 hours
last_memory_check = 0
last_gc_time = 0

# Market mode globals
is_full_mode = False
market_checker_thread = None
app_process = None
next_scheduled_check = 0  # Timestamp for next market check

def is_market_open():
    """
    Check if the market is currently open.
    Returns True if it's a weekday (Monday-Friday), not a holiday, and time is between 9:00 AM to 3:30 PM IST.
    """
    # Import here to avoid circular imports
    from nse_holidays import is_market_holiday
    
    # IMPORTANT: Always use IST timezone for market operations
    now = datetime.now(IST)
    logger.debug(f"Current date/time (IST): {now}")
    
    # Check if it's a weekday (0 is Monday, 6 is Sunday)
    weekday = now.weekday()
    if weekday > 4:  # Saturday or Sunday
        logger.debug(f"Market closed: Weekend (weekday {weekday})")
        return False
    
    # Force date to have the correct timezone
    date_to_check = now.date()
    
    # Check if it's a holiday
    if is_market_holiday(date_to_check):
        logger.debug(f"Market closed: Holiday on {date_to_check}")
        return False
    
    # Create datetime objects for market open (9:00 AM) and close (3:30 PM)
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if current time is within market hours
    market_status = market_open <= now <= market_close
    if market_status:
        logger.debug(f"Market open: Within trading hours ({now.strftime('%H:%M')})")
    else:
        logger.debug(f"Market closed: Outside trading hours ({now.strftime('%H:%M')})")
    
    return market_status

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

def restart_application(use_full_mode):
    """
    Restart the application in the appropriate mode
    """
    global app_process, is_full_mode
    
    # If there's a current process, terminate it
    if app_process:
        try:
            app_process.terminate()
            app_process.wait(timeout=10)
            logger.info("Terminated existing application process")
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
            try:
                import signal
                app_process.send_signal(signal.SIGKILL)
                logger.info("Force killed application process")
            except:
                logger.error("Failed to force kill process")
    
    # Start the new process
    try:
        logger.info(f"Starting application in {'FULL' if use_full_mode else 'MINIMAL'} mode")
        
        # Set environment variable to indicate mode
        os.environ["MARKET_MODE"] = "FULL" if use_full_mode else "MINIMAL"
        
        # Start the application process with production-ready server
        if use_full_mode:
            # Check if we're on Windows
            if sys.platform.startswith('win'):
                # Use Flask's built-in server on Windows
                app_process = subprocess.Popen([sys.executable, "chartink_webhook.py"])
                logger.info("Using Flask development server on Windows instead of gunicorn")
            else:
                # Full mode with gunicorn for production server (Linux/Mac)
                app_process = subprocess.Popen(["gunicorn", "--bind", "0.0.0.0:5000", "chartink_webhook:app"])
        else:
            # Minimal mode can use regular python to save resources
            app_process = subprocess.Popen([sys.executable, "chartink_webhook.py"])
        
        # Update mode flag
        old_mode = is_full_mode
        is_full_mode = use_full_mode
        
        # Only send notification if this is a change from minimal to full mode or vice versa,
        # not when restarting in the same mode
        if use_full_mode != old_mode:
            # Send notification about mode change
            try:
                from telegram_notifier import TelegramNotifier
                telegram = TelegramNotifier()
                now = datetime.now(IST)
                
                if use_full_mode:
                    message = f"The trading bot has switched to FULL mode as the market is now open.\n" \
                            f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n\n" \
                            f"Trading operations have resumed automatically."
                    
                    telegram.send_formatted_notification(
                        "Market Mode: FULL", 
                        message,
                        status="market_open"
                    )
                    logger.info(f"Sent mode change notification via Telegram: FULL mode")
                else:
                    # We'll only log this but not send a telegram notification for minimal mode
                    # to avoid spamming the group
                    logger.info(f"Switched to MINIMAL mode - market is now closed")
                
            except Exception as e:
                logger.error(f"Failed to send mode change notification: {e}")
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")

def calculate_time_until_next_check():
    """
    Calculate the optimal time until the next market status check.
    Returns time in seconds until the next check should occur.
    This is more efficient than checking at fixed intervals.
    """
    now = datetime.now(IST)
    
    # If it's a weekend (Saturday or Sunday)
    if now.weekday() > 4:
        # Calculate time until Monday 8:45 AM
        days_until_monday = 7 - now.weekday() if now.weekday() == 6 else 2
        next_check = now.replace(hour=8, minute=45, second=0, microsecond=0) + timedelta(days=days_until_monday)
        seconds_until_check = (next_check - now).total_seconds()
        return max(seconds_until_check, 3600)  # Check at least once an hour even on weekends
    
    # If it's a holiday
    from nse_holidays import is_market_holiday
    if is_market_holiday(now.date()):
        # Check once at 8:45 AM tomorrow
        next_check = (now + timedelta(days=1)).replace(hour=8, minute=45, second=0, microsecond=0)
        seconds_until_check = (next_check - now).total_seconds()
        return max(seconds_until_check, 3600)  # Check at least once an hour on holidays
    
    # During trading days, check at specific times
    current_hour = now.hour
    current_minute = now.minute
    
    # Before market opens (midnight to 8:45 AM)
    if current_hour < 8 or (current_hour == 8 and current_minute < 45):
        # Schedule next check at 8:45 AM for pre-market preparation
        next_check = now.replace(hour=8, minute=45, second=0, microsecond=0)
        return (next_check - now).total_seconds()
    
    # Just before market opens (8:45 AM to 9:00 AM)
    if current_hour == 8 and current_minute >= 45:
        # Check every minute until market opens
        return 60
    
    # During market hours (9:00 AM to 3:30 PM)
    if (current_hour == 9 and current_minute >= 0) or (current_hour > 9 and current_hour < 15) or (current_hour == 15 and current_minute <= 30):
        # Check every 15 minutes during market hours
        return 15 * 60
    
    # Just after market closes (3:30 PM to 3:45 PM)
    if current_hour == 15 and current_minute > 30 and current_minute < 45:
        # Check every minute to catch the transition
        return 60
    
    # After market closes (3:45 PM to midnight)
    # Calculate time until tomorrow 8:45 AM
    next_check = (now + timedelta(days=1)).replace(hour=8, minute=45, second=0, microsecond=0)
    seconds_until_check = (next_check - now).total_seconds()
    return seconds_until_check

def market_checker():
    """
    Thread that intelligently checks market hours and restarts the app if needed
    """
    global next_scheduled_check
    last_market_status = None  # Track last market status to avoid redundant logging
    
    while True:
        current_time = time.time()
        
        # Only check if it's time for the next scheduled check
        if current_time >= next_scheduled_check:
            try:
                # Check if market is open
                market_open = is_market_open()
                
                # If status changed or mode doesn't match market status, take action
                if market_open != is_full_mode:
                    # Only log status change if it actually changed
                    if market_open != last_market_status:
                        logger.info(f"Market status changed: {'open' if market_open else 'closed'}, restarting application")
                    restart_application(market_open)
                
                # Update last status
                last_market_status = market_open
                
                # Schedule next check based on current time and market status
                sleep_time = calculate_time_until_next_check()
                logger.info(f"Next market check scheduled in {sleep_time//60} minutes, {sleep_time%60} seconds")
                next_scheduled_check = current_time + sleep_time
                
            except Exception as e:
                logger.error(f"Error in market checker: {e}")
                # In case of error, check again in 5 minutes
                next_scheduled_check = current_time + 300
        
        # Optimize memory
        optimize_memory()
        
        # Sleep a short time to prevent CPU spinning while allowing quick checks
        # when needed (like during market open/close transitions)
        time.sleep(30)

def wait_for_market_open():
    """Wait until the market opens by calculating sleep time - with optimized resource usage"""
    global market_checker_thread, next_scheduled_check
    
    # Initialize next check time to now
    next_scheduled_check = time.time()
    
    # Start the market checker thread if not already running
    if market_checker_thread is None or not market_checker_thread.is_alive():
        market_checker_thread = threading.Thread(target=market_checker, daemon=True)
        market_checker_thread.start()
        logger.info("Started market checker thread")
    
    # Initial check - if market is open, break, otherwise continue waiting
    if is_market_open():
        logger.info("Market is now open. Starting application...")
        
        # Send notification that market is now open
        try:
            from telegram_notifier import TelegramNotifier
            telegram = TelegramNotifier()
            now = datetime.now(IST)
            
            message = f"The trading bot has started in full mode as the market is now open.\n" \
                    f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n\n" \
                    f"Trading operations have resumed automatically."
            
            telegram.send_formatted_notification(
                "Market Now Open", 
                message,
                status="market_open"
            )
            logger.info("Sent market open notification via Telegram")
        except Exception as e:
            logger.error(f"Failed to send market open notification: {e}")
        
        # Start in full mode
        restart_application(True)
    else:
        logger.info("Market is currently closed. Starting application in minimal mode...")
        
        # Start in minimal mode
        restart_application(False)
    
    # Keep the main thread alive
    try:
        # Monitor the app process
        while app_process.poll() is None:
            time.sleep(1)
        
        # If we get here, the process terminated unexpectedly
        logger.error(f"Application process terminated unexpectedly with code {app_process.returncode}")
        
        # Restart the application in the current mode
        restart_application(is_full_mode)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        if app_process:
            app_process.terminate()
    except Exception as e:
        logger.error(f"Error in main thread: {e}")

def main():
    """
    Main function that starts either the full or standby version of the application.
    """
    logger.info("Using file-based storage instead of database to reduce costs")
    
    # Initial market hours check
    market_open = is_market_open()
    
    if market_open:
        logger.info("Market is open. Starting full application with trading capabilities.")
        
        # Set market mode environment variable
        os.environ["MARKET_MODE"] = "FULL"
    else:
        logger.info("Market is closed. Entering standby mode with minimal resource usage.")
        
        # Set market mode environment variable
        os.environ["MARKET_MODE"] = "MINIMAL"
        
        # Prewarm Telegram for notifications
        try:
            from telegram_notifier import TelegramNotifier
            TelegramNotifier()
            logger.info("Prewarmed Telegram notifier")
        except Exception as e:
            logger.error(f"Failed to prewarm Telegram notifier: {e}")
        
        # Minimize imports to reduce memory usage
        logger.info("Launching minimal version of the app during market closure")
    
    # The main waiting function also acts as the process monitor
    wait_for_market_open()

if __name__ == "__main__":
    main() 