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
    
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
    
    def is_enabled(self):
        """Check if Telegram notifications are enabled"""
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, message, parse_mode="HTML"):
        """Send a message to the configured Telegram chat"""
        if not self.is_enabled():
            logger.warning("Telegram notifications not configured - message not sent")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def notify_trade(self, trade_details):
        """Send a notification about a new trade"""
        if not self.is_enabled():
            return False
        
        try:
            symbol = trade_details.get("stock", "")
            signal = trade_details.get("signal", "")
            price = trade_details.get("price", 0)
            quantity = trade_details.get("quantity", 0)
            scanner = trade_details.get("scanner", "")
            order_id = trade_details.get("order_id", "")
            
            emoji = "🟢" if signal == "BUY" else "🔴"
            
            message = (
                f"{emoji} <b>New Trade Executed</b>\n\n"
                f"<b>Signal:</b> {signal}\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> ₹{price:.2f}\n"
                f"<b>Quantity:</b> {quantity}\n"
                f"<b>Total Value:</b> ₹{price * quantity:.2f}\n"
                f"<b>Scanner:</b> {scanner}\n"
                f"<b>Order ID:</b> {order_id}\n"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            return self.send_message(message)
        except Exception as e:
            logger.error(f"Error formatting trade notification: {e}")
            return False
    
    def notify_chartink_alert(self, alert_data):
        """Send a notification about a ChartInk alert"""
        if not self.is_enabled():
            return False
        
        try:
            scan_name = alert_data.get("scan_name", "")
            stocks = alert_data.get("stocks", "").split(",")
            prices = alert_data.get("trigger_prices", "").split(",")
            
            # Determine if it's a buy or sell signal based on scan name
            scan_lower = scan_name.lower()
            is_buy = "buy" in scan_lower or "bullish" in scan_lower or "breakout" in scan_lower
            is_sell = "sell" in scan_lower or "bearish" in scan_lower or "short" in scan_lower
            
            emoji = "🟢" if is_buy else ("🔴" if is_sell else "⚪")
            
            message = (
                f"{emoji} <b>ChartInk Alert: {scan_name}</b>\n\n"
                f"<b>Triggered at:</b> {alert_data.get('triggered_at', '')}\n"
                f"<b>Alert:</b> {alert_data.get('alert_name', '')}\n\n"
                "<b>Stocks:</b>\n"
            )
            
            for i, stock in enumerate(stocks):
                if stock.strip():
                    price_text = prices[i].strip() if i < len(prices) else "N/A"
                    message += f"• {stock.strip()} - ₹{price_text}\n"
            
            return self.send_message(message)
        except Exception as e:
            logger.error(f"Error formatting ChartInk alert notification: {e}")
            return False
    
    def notify_auth_status(self, is_authenticated, user=None):
        """Send a notification about authentication status"""
        if not self.is_enabled():
            return False
        
        try:
            if is_authenticated:
                message = (
                    f"🔑 <b>Zerodha Authentication Successful</b>\n\n"
                    f"<b>User:</b> {user}\n"
                    f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                message = (
                    f"⚠️ <b>Zerodha Authentication Required</b>\n\n"
                    f"Your token has expired. Please login at your app URL."
                )
            
            return self.send_message(message)
        except Exception as e:
            logger.error(f"Error formatting auth notification: {e}")
            return False
    
    def send_test_message(self):
        """Send a test message to verify Telegram configuration"""
        message = (
            f"✅ <b>Test Message</b>\n\n"
            f"Your Telegram notifications are configured correctly.\n"
            f"You will receive alerts for trades and ChartInk signals.\n\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return self.send_message(message) 