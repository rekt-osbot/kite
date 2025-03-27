import os
import logging
import json
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Class to handle Telegram notifications for trades and alerts
    """
    
    def __init__(self):
        """Initialize Telegram notifier with environment variables"""
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram notifications disabled: missing bot token or chat ID")
    
    def send_notification(self, message, parse_mode="Markdown"):
        """Send a notification to the configured Telegram chat"""
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            logger.info("Telegram message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def notify_chartink_alert(self, alert_data):
        """Send notification about a ChartInk alert"""
        if not self.enabled:
            return False
        
        try:
            scan_name = alert_data.get('scan_name', 'Unknown Scanner')
            alert_name = alert_data.get('alert_name', 'Unknown Alert')
            triggered_at = alert_data.get('triggered_at', 'Unknown Time')
            stocks = alert_data.get('stocks', [])
            prices = alert_data.get('trigger_prices', [])
            action = alert_data.get('action', 'BUY')
            
            # Handle both string and list formats
            if isinstance(stocks, str):
                stocks = stocks.split(',')
            if isinstance(prices, str):
                prices = prices.split(',')
            
            # Create formatted message
            emoji = "🟢" if action == "BUY" else "🔴"
            message = f"{emoji} *{action} ALERT: {alert_name}*\n\n"
            message += f"*Strategy:* {scan_name}\n"
            message += f"*Triggered at:* {triggered_at}\n\n"
            message += f"*Stocks:*\n"
            
            for i, stock in enumerate(stocks):
                stock = stock.strip()
                if not stock:
                    continue
                
                price = prices[i].strip() if i < len(prices) else "N/A"
                message += f"- *{stock}*: ₹{price}\n"
            
            return self.send_notification(message)
        except Exception as e:
            logger.error(f"Failed to create chartink alert notification: {e}")
            return False
    
    def notify_trade(self, trade_data):
        """Send notification about a trade execution"""
        if not self.enabled:
            return False
        
        try:
            stock = trade_data.get('stock', 'Unknown')
            signal = trade_data.get('signal', 'Unknown')
            price = trade_data.get('price', 0)
            quantity = trade_data.get('quantity', 0)
            scanner = trade_data.get('scanner', 'Unknown')
            order_id = trade_data.get('order_id', 'Unknown')
            
            # Create formatted message
            emoji = "🟢" if signal == "BUY" else "🔴"
            message = f"{emoji} *{signal} ORDER PLACED*\n\n"
            message += f"*Stock:* {stock}\n"
            message += f"*Price:* ₹{price}\n"
            message += f"*Quantity:* {quantity}\n"
            message += f"*Strategy:* {scanner}\n"
            message += f"*Order ID:* `{order_id}`\n"
            
            return self.send_notification(message)
        except Exception as e:
            logger.error(f"Failed to create trade notification: {e}")
            return False
    
    def notify_auth_status(self, is_authenticated, username="User"):
        """Send notification about authentication status"""
        if not self.enabled:
            return False
        
        try:
            if is_authenticated:
                message = f"✅ *Authentication Successful*\n\n"
                message += f"User *{username}* has successfully logged in to Zerodha."
            else:
                message = f"⚠️ *Authentication Required*\n\n"
                message += f"Zerodha authentication token has expired. Please log in again."
            
            return self.send_notification(message)
        except Exception as e:
            logger.error(f"Failed to create auth status notification: {e}")
            return False
    
    def send_test_message(self):
        """Send a test message to verify Telegram configuration"""
        test_message = "🧪 *Test Message*\n\nThis is a test message from your trading application to verify Telegram notifications are working correctly."
        return self.send_notification(test_message) 