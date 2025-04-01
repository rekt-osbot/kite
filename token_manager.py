#!/usr/bin/env python
"""
Token Manager Module

Handles Zerodha API tokens specific to market hours operation.
Zerodha tokens expire daily at 6 AM IST, which falls during trading hours (9 AM - 3:30 PM IST).
"""
import os
import time
import pytz
from datetime import datetime, timedelta
from file_storage import storage
from dependency_resolver import lazy_import
from logger import get_logger  # Import our centralized logger

# Lazy imports to avoid circular dependencies
TelegramNotifier = lazy_import('telegram_notifier', 'TelegramNotifier')

# Get logger for this module
logger = get_logger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Constants
TOKEN_EXPIRY_HOUR = 6  # 6 AM IST daily
MARKET_OPEN_HOUR = 9   # 9 AM IST
MARKET_CLOSE_HOUR = 15 # 3 PM IST (15:30 actually)

class TokenManager:
    """Manages Zerodha API tokens with market hours in mind"""
    
    def __init__(self):
        """Initialize the token manager"""
        self.is_authenticated = False
        self.username = None
        self.access_token = None
        self.expiry_time = None
        self.trading_disabled = False
        self.load_token()
    
    def load_token(self):
        """Load token from storage and set expiry time based on 6 AM rule"""
        token_data = storage.get_token()
        if not token_data:
            logger.warning("No token found in storage")
            self.is_authenticated = False
            return False
        
        self.username = token_data.get('username')
        self.access_token = token_data.get('access_token')
        
        # Calculate when this token expires (6 AM IST today or tomorrow)
        now = datetime.now(IST)
        self.expiry_time = now.replace(hour=TOKEN_EXPIRY_HOUR, minute=0, second=0, microsecond=0)
        
        # If current time is past 6 AM, token expires at 6 AM tomorrow
        if now.hour >= TOKEN_EXPIRY_HOUR:
            self.expiry_time = self.expiry_time + timedelta(days=1)
        
        # Check if token is still valid
        self.is_authenticated = now < self.expiry_time
        
        if self.is_authenticated:
            logger.info(f"Loaded valid token for {self.username}, expires at {self.expiry_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
        else:
            logger.warning(f"Loaded expired token for {self.username}")
            self.trading_disabled = True
        
        return self.is_authenticated
    
    def save_token(self, user_id, username, access_token):
        """Save a new token with expiry time set to 6 AM IST"""
        now = datetime.now(IST)
        
        # Calculate expiration time (6 AM IST)
        expires_at = now.replace(hour=TOKEN_EXPIRY_HOUR, minute=0, second=0, microsecond=0)
        if now.hour >= TOKEN_EXPIRY_HOUR:
            expires_at = expires_at + timedelta(days=1)
        
        # Calculate hours until expiry for storage
        expires_in_hours = (expires_at - now).total_seconds() / 3600
        
        # Save to storage
        token_data = storage.save_token(
            user_id=user_id,
            username=username,
            access_token=access_token,
            expires_in_hours=expires_in_hours
        )
        
        # Update in-memory state
        self.username = username
        self.access_token = access_token
        self.expiry_time = expires_at
        self.is_authenticated = True
        self.trading_disabled = False
        
        # Log and notify
        logger.info(f"Saved new token for {username}, expires at {expires_at.strftime('%Y-%m-%d %H:%M:%S IST')}")
        self._send_token_notification(is_new=True)
        
        return token_data
    
    def get_token(self):
        """Get the current access token if valid"""
        self.check_token()  # Verify token is still valid
        return self.access_token if self.is_authenticated else None
    
    def check_token(self):
        """Check if the token is valid based on the 6 AM expiry rule"""
        now = datetime.now(IST)
        
        # If no token, return immediately
        if not self.access_token:
            self.is_authenticated = False
            return False
            
        # If we have an expiry time, check against it
        if self.expiry_time:
            # Token expired
            if now >= self.expiry_time:
                if self.is_authenticated:  # Only log and notify if changing state
                    logger.warning(f"Token for {self.username} has expired at 6 AM IST")
                    self.is_authenticated = False
                    self.trading_disabled = True
                    self._send_token_notification(is_expired=True)
                return False
            
            # Token will expire during market hours today
            if (self.expiry_time.day == now.day and 
                now.hour < TOKEN_EXPIRY_HOUR and 
                MARKET_OPEN_HOUR <= TOKEN_EXPIRY_HOUR):
                # Send warning during market hours as we approach 6 AM
                if now.hour >= MARKET_OPEN_HOUR:
                    minutes_to_expiry = (self.expiry_time - now).total_seconds() / 60
                    if minutes_to_expiry <= 60:  # Last hour warning
                        self._send_expiry_warning(minutes_to_expiry / 60)
        
        return self.is_authenticated
    
    def is_trading_enabled(self):
        """Check if trading is enabled based on token validity"""
        # First verify token is valid
        self.check_token()
        
        # Return trading status
        return self.is_authenticated and not self.trading_disabled
    
    def _send_token_notification(self, is_new=False, is_expired=False):
        """Send notification about token status"""
        try:
            telegram = TelegramNotifier()
            
            # Skip login notification - commented out as we don't need login notifications
            if is_new:
                # Login notification has been disabled as requested
                # We only want to keep critical notifications like token expiry
                pass
                
            elif is_expired:
                app_url = os.getenv("APP_URL", "")
                login_url = f"{app_url}/auth/refresh" if app_url else "/auth/refresh"
                
                message = f"⚠️ <b>Token Expired - Trading Disabled</b>\n\n"
                message += f"Your Zerodha API token has expired at 6 AM IST. Trading operations have been disabled.\n\n"
                message += f"<b>To continue trading:</b>\n"
                message += f"1. <a href='{login_url}'>Click here to login</a> with your Zerodha credentials\n"
                message += f"2. Complete the authentication process\n"
                message += f"3. Trading will resume automatically once authenticated\n\n"
                
                telegram.send_message(message)
        
        except Exception as e:
            logger.error(f"Error sending token notification: {e}")
    
    def _send_expiry_warning(self, hours_left):
        """Send warning when token is about to expire (specifically for market hours)"""
        try:
            # Format time nicely
            minutes_left = int(hours_left * 60)
            time_left_str = f"{minutes_left} minutes"
            
            app_url = os.getenv("APP_URL", "")
            login_url = f"{app_url}/auth/refresh" if app_url else "/auth/refresh"
            
            message = f"⏰ <b>Urgent: Token Expiring During Market Hours</b>\n\n"
            message += f"Your Zerodha API token will expire in <b>{time_left_str}</b> at 6 AM IST.\n\n"
            message += f"<b>To prevent trading interruption:</b>\n"
            message += f"1. <a href='{login_url}'>Click here to login</a> with your Zerodha credentials\n"
            message += f"2. Complete the authentication process\n\n"
            
            telegram = TelegramNotifier()
            telegram.send_message(message)
            
            logger.info(f"Sent market hours token expiry warning: {time_left_str} remaining")
        
        except Exception as e:
            logger.error(f"Error sending expiry warning: {e}")
    
    def get_status_info(self):
        """Get detailed token status information"""
        now = datetime.now(IST)
        self.check_token()  # Ensure status is up to date
        
        status = {
            "authenticated": self.is_authenticated,
            "trading_enabled": self.is_authenticated and not self.trading_disabled,
            "username": self.username,
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        }
        
        if self.expiry_time:
            # Calculate time until expiry
            time_until_expiry = self.expiry_time - now
            hours_until_expiry = max(0, time_until_expiry.total_seconds() / 3600)
            
            # Add expiry information
            status.update({
                "expires_at": self.expiry_time.strftime("%Y-%m-%d %H:%M:%S IST"),
                "hours_until_expiry": round(hours_until_expiry, 2),
                "expires_during_market_hours": (
                    self.expiry_time.day == now.day and
                    MARKET_OPEN_HOUR <= TOKEN_EXPIRY_HOUR <= MARKET_CLOSE_HOUR
                )
            })
            
            # Add trading day status
            if self.is_authenticated:
                if status.get("expires_during_market_hours"):
                    status["trading_day_status"] = "Requires renewal before 6 AM"
                else:
                    status["trading_day_status"] = "Valid for entire trading day"
            else:
                status["trading_day_status"] = "Token expired"
        
        return status

# Create a global instance
token_manager = TokenManager() 