#!/usr/bin/env python
"""
Test the market status functions with holidays
"""
import logging
import pytz
from datetime import datetime
from nse_holidays import is_market_holiday, get_next_trading_day, fetch_nse_holidays
from railway_start import is_market_open, calculate_next_market_open

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

def main():
    """Test the market status functions"""
    # Current status
    now = datetime.now(IST)
    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Check if market is open
    market_open = is_market_open()
    print(f"Is market open: {market_open}")
    
    # Check if today is a holiday
    is_holiday = is_market_holiday()
    print(f"Is today a holiday: {is_holiday}")
    
    # Get next trading day
    next_trading = get_next_trading_day()
    print(f"Next trading day: {next_trading}")
    
    # Calculate next market open time
    next_open = calculate_next_market_open()
    next_open_str = next_open.strftime('%Y-%m-%d %H:%M:%S IST') if next_open else "Unknown"
    print(f"Next market open time: {next_open_str}")
    
    # Determine reason for market closure
    closure_reason = "Market is currently open"
    if not market_open:
        if now.weekday() > 4:
            closure_reason = "Market is closed for the weekend"
        elif is_holiday:
            # Get the holiday description
            holidays = fetch_nse_holidays()
            date_str = now.strftime('%Y-%m-%d')
            for holiday in holidays:
                if holiday.get('date') == date_str:
                    closure_reason = f"Market is closed for {holiday.get('description')}"
                    break
        else:
            # Must be outside trading hours
            closure_reason = "Market is closed outside trading hours"
        
    print(f"Market status: {closure_reason}")
    
def test_holiday_notification():
    """Test sending a Telegram notification about market holiday"""
    from telegram_notifier import TelegramNotifier
    
    try:
        # Initialize Telegram notifier
        telegram = TelegramNotifier()
        
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
        
        # Send notification
        message = f"🧪 <b>TEST: Market Closed: {holiday_desc}</b>\n\n" \
                f"This is a TEST notification. The trading bot has been shut down for today due to a market holiday.\n" \
                f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                f"Next market open: {next_open_str}\n\n" \
                f"The bot will automatically restart when the market reopens."
        
        success = telegram.send_message(message)
        print(f"Test notification sent: {success}")
        return success
    except Exception as e:
        print(f"Error sending test notification: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test-notification":
        test_holiday_notification()
    else:
        main() 