import os
import logging
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    A class to handle Telegram notifications for the trading system.
    """
    
    def __init__(self, token=None, chat_id=None):
        # Load environment variables
        load_dotenv()
        
        # Initialize logger
        self.logger = logging.getLogger('telegram_notifier')
        
        # Set Telegram API token and chat ID
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        # Initialize
        self.enabled = True
        self._check_config()
    
    def update_config(self, token=None, chat_id=None, enabled=True):
        """Update the configuration for the Telegram notifier"""
        if token:
            self.token = token
            self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        if chat_id:
            self.chat_id = chat_id
        
        self.enabled = enabled
        self._check_config()
    
    def _check_config(self):
        """Check if the configuration is valid"""
        if not self.token or not self.chat_id:
            self.logger.warning("Telegram notifications disabled: Missing API token or chat ID")
            self.enabled = False
    
    def is_enabled(self):
        """Return whether the notifier is enabled with valid configuration"""
        return self.enabled
    
    def send_message(self, message, disable_notification=False):
        """
        Send a message to the configured Telegram chat.
        
        Args:
            message (str): The message text to send.
            disable_notification (bool): Whether to send the message silently.
        
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self.enabled:
            self.logger.debug("Telegram notifications are disabled. Message not sent.")
            return False
        
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_notification": disable_notification
            }
            
            response = requests.post(f"{self.base_url}/sendMessage", json=payload)
            
            if response.status_code == 200:
                self.logger.debug(f"Telegram message sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Telegram message: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def notify_chartink_alert(self, scan_name, stocks, prices):
        """
        Send a notification for a ChartInk alert.
        
        Args:
            scan_name (str): The name of the scan that triggered.
            stocks (list): List of stocks that matched the scan.
            prices (list): List of prices corresponding to the stocks.
        
        Returns:
            bool: True if the notification was sent successfully, False otherwise.
        """
        try:
            # Determine if this is a buy or sell signal based on the scan name
            is_buy_signal = any(word in scan_name.lower() for word in ["buy", "long", "bullish", "breakout", "up"])
            is_sell_signal = any(word in scan_name.lower() for word in ["sell", "short", "bearish", "breakdown", "down"])
            
            if is_buy_signal:
                signal_icon = "🟢"
                action = "BUY"
            elif is_sell_signal:
                signal_icon = "🔴"
                action = "SELL"
            else:
                signal_icon = "🔔"
                action = "ALERT"
            
            # Create the message
            message = f"{signal_icon} <b>ChartInk {action} Alert</b>\n\n"
            message += f"<b>Scan:</b> {scan_name}\n"
            message += f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += "<b>Stocks:</b>\n"
            
            for i, (stock, price) in enumerate(zip(stocks, prices)):
                message += f"- <b>{stock}</b>: ₹{price}\n"
            
            return self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to create chartink alert notification: {e}")
            return False
    
    def notify_trade(self, transaction_type, symbol, quantity, price, order_id):
        """
        Send a notification for a trade.
        
        Args:
            transaction_type (str): BUY or SELL.
            symbol (str): The trading symbol.
            quantity (int): The quantity traded.
            price (float): The trade price.
            order_id (str): The order ID.
        
        Returns:
            bool: True if the notification was sent successfully, False otherwise.
        """
        try:
            # Determine emoji based on transaction type
            if transaction_type.upper() == "BUY":
                emoji = "🟢"
            else:
                emoji = "🔴"
            
            # Create the message
            message = f"{emoji} <b>{transaction_type.upper()} Order Placed</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Quantity:</b> {quantity}\n"
            message += f"<b>Price:</b> ₹{price}\n"
            message += f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"<b>Order ID:</b> <code>{order_id}</code>\n"
            
            return self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to create trade notification: {e}")
            return False
    
    def notify_auth_status(self, is_authenticated, username="User"):
        """
        Send a notification about authentication status.
        
        Args:
            is_authenticated (bool): Whether authentication was successful.
            username (str): The username if authenticated.
        
        Returns:
            bool: True if the notification was sent successfully, False otherwise.
        """
        try:
            if is_authenticated:
                message = f"🔐 <b>Authentication Successful</b>\n\n"
                message += f"User <b>{username}</b> has successfully logged in."
            else:
                message = f"⚠️ <b>Authentication Failed</b>\n\n"
                message += f"Zerodha authentication token has expired. Please log in again."
            
            return self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to create auth status notification: {e}")
            return False
    
    def send_test_message(self):
        """Send a test message to verify Telegram configuration"""
        test_message = "🧪 <b>Test Message</b>\n\nThis is a test message from your trading application to verify Telegram notifications are working correctly."
        return self.send_message(test_message)

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the notification
    notifier = TelegramNotifier()
    notifier.send_test_message() 