#!/usr/bin/env python
"""
Module to fetch and verify NSE holidays
"""
import os
import json
import logging
import requests
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

# Path to cache file
HOLIDAYS_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nse_holidays.json')

def fetch_nse_holidays():
    """
    Fetch NSE holidays from the NSE website
    Returns a list of holiday dates for the current year
    """
    current_year = datetime.now(IST).year
    holidays = []
    
    try:
        # Try to load from cache first
        if os.path.exists(HOLIDAYS_CACHE_FILE):
            with open(HOLIDAYS_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                # Check if cache is for current year and not expired
                if cache_data.get('year') == current_year and cache_data.get('expires') > datetime.now().timestamp():
                    logger.info(f"Using cached NSE holidays for {current_year}")
                    return cache_data.get('holidays', [])
        
        # NSE holiday list URL - this may change and need updating
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json'
        }
        
        print(f"Fetching NSE holidays for {current_year} from {url}")
        logger.info(f"Fetching NSE holidays for {current_year}")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Response status code: {response.status_code}")
        response.raise_for_status()
        
        data = response.json()
        print(f"Response data keys: {data.keys()}")
        
        # Extract holiday dates - adjust this based on the actual JSON structure
        for holiday in data.get('CM', []):  # CM refers to Capital Market segment
            holiday_date_str = holiday.get('tradingDate')
            holiday_desc = holiday.get('description', '')
            
            if holiday_date_str:
                # Parse date from the format provided by NSE
                try:
                    # Adjust the date parsing format based on NSE's date format
                    holiday_date = datetime.strptime(holiday_date_str, '%d-%b-%Y').strftime('%Y-%m-%d')
                    holidays.append({
                        'date': holiday_date,
                        'description': holiday_desc
                    })
                    print(f"Added holiday: {holiday_date} - {holiday_desc}")
                except ValueError as e:
                    logger.error(f"Failed to parse holiday date {holiday_date_str}: {e}")
                    print(f"Failed to parse holiday date {holiday_date_str}: {e}")
        
        # Cache the results for 24 hours
        cache_data = {
            'year': current_year,
            'expires': (datetime.now() + timedelta(hours=24)).timestamp(),
            'holidays': holidays
        }
        
        try:
            os.makedirs(os.path.dirname(HOLIDAYS_CACHE_FILE), exist_ok=True)
            with open(HOLIDAYS_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            logger.info(f"Cached {len(holidays)} NSE holidays for {current_year}")
        except Exception as e:
            logger.error(f"Failed to cache holidays: {e}")
            print(f"Failed to cache holidays: {e}")
        
        return holidays
    
    except Exception as e:
        logger.error(f"Error fetching NSE holidays: {e}")
        print(f"Error fetching NSE holidays: {e}")
        
        # If error occurs, try to use cached data even if expired
        try:
            if os.path.exists(HOLIDAYS_CACHE_FILE):
                with open(HOLIDAYS_CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                    if cache_data.get('year') == current_year:
                        logger.info(f"Using expired cached NSE holidays due to fetch error")
                        return cache_data.get('holidays', [])
        except Exception as cache_err:
            logger.error(f"Failed to load cached holidays: {cache_err}")
            print(f"Failed to load cached holidays: {cache_err}")
        
        return []

def is_market_holiday(date=None):
    """
    Check if the given date (or today if None) is an NSE holiday
    Returns True if it's a holiday, False otherwise
    """
    if date is None:
        date = datetime.now(IST).date()
    else:
        # Ensure we're working with a date object
        if isinstance(date, datetime):
            date = date.date()
    
    date_str = date.strftime('%Y-%m-%d')
    print(f"Checking if {date_str} is a holiday")
    
    # Get holidays
    holidays = fetch_nse_holidays()
    print(f"Found {len(holidays)} holidays in the database")
    
    # Check if date is in holidays
    for holiday in holidays:
        if holiday.get('date') == date_str:
            print(f"{date_str} is an NSE holiday: {holiday.get('description')}")
            logger.info(f"{date_str} is an NSE holiday: {holiday.get('description')}")
            return True
    
    print(f"{date_str} is NOT an NSE holiday")
    return False

def get_next_trading_day(date=None):
    """
    Get the next trading day from the given date (or today if None)
    Accounts for weekends and holidays
    """
    if date is None:
        date = datetime.now(IST).date()
    else:
        # Ensure we're working with a date object
        if isinstance(date, datetime):
            date = date.date()
    
    print(f"Finding next trading day after {date}")
    
    # Start with next day
    next_day = date + timedelta(days=1)
    
    # Keep checking until we find a trading day
    max_attempts = 30  # Safety to avoid infinite loop
    attempts = 0
    
    while attempts < max_attempts:
        attempts += 1
        # Check if it's a weekend
        if next_day.weekday() > 4:  # Saturday or Sunday
            print(f"{next_day} is a weekend, checking next day")
            next_day += timedelta(days=1)
            continue
        
        # Check if it's a holiday
        if is_market_holiday(next_day):
            print(f"{next_day} is a holiday, checking next day")
            next_day += timedelta(days=1)
            continue
        
        # Found a trading day
        print(f"Next trading day is {next_day}")
        return next_day
    
    print("Warning: Reached maximum attempts without finding a trading day")
    return next_day  # Return the last checked day as a fallback

if __name__ == "__main__":
    print("================================")
    print("NSE Holiday Checker Test")
    print("================================")
    
    # Test the module
    print("\nFetching NSE holidays...")
    holidays = fetch_nse_holidays()
    print(f"\nNSE Holidays for {datetime.now(IST).year}:")
    for holiday in holidays:
        print(f"{holiday['date']} - {holiday['description']}")
    
    # Test if today is a holiday
    today = datetime.now(IST).date()
    print(f"\nChecking if today ({today}) is a holiday...")
    if is_market_holiday():
        print(f"Result: Today ({today}) is an NSE holiday")
    else:
        print(f"Result: Today ({today}) is NOT an NSE holiday")
    
    # Get next trading day
    print("\nCalculating next trading day...")
    next_trading = get_next_trading_day()
    print(f"Result: Next trading day is {next_trading}")
    
    print("\nTest complete.") 