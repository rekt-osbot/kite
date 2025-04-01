import os
import logging
import json
import requests
from datetime import datetime, date
from dotenv import load_dotenv
from telegram import Bot

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Notification service using Telegram bot API
    """
    def __init__(self):
        """Initialize Telegram bot connection"""
        # Get credentials from environment variables
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Verify credentials
        if not self.telegram_token or not self.telegram_chat_id:
            self.logger.warning("Telegram credentials not configured - notifications disabled")
            self.enabled = False
            return
            
        # Initialize bot
        try:
            self.bot = Bot(token=self.telegram_token)
            self.enabled = True
            self.logger.info("Telegram notification service initialized")
        except Exception as e:
            self.logger.error(f"Telegram initialization failed: {str(e)}")
            self.enabled = False
    
    def send_message(self, message, disable_notification=False):
        """
        Send message to Telegram chat
        """
        if not self.enabled:
            self.logger.warning("Telegram notifications disabled - message not sent")
            return False
            
        try:
            self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode="HTML",
                disable_notification=disable_notification
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {str(e)}")
            return False
    
    def send_formatted_notification(self, title, message, status="info", disable_notification=False):
        """
        Send a beautifully formatted notification message to Telegram
        
        Parameters:
        - title: The notification title
        - message: The main message content
        - status: One of "success", "warning", "error", "info"
        - disable_notification: Whether to send silently
        """
        if not self.enabled:
            self.logger.warning("Telegram notifications disabled - message not sent")
            return False
        
        # Status icons and styling
        status_formats = {
            "success": {"icon": "✅", "header": "🟢"},
            "warning": {"icon": "⚠️", "header": "🟠"},
            "error": {"icon": "❌", "header": "🔴"},
            "info": {"icon": "ℹ️", "header": "🔵"},
            "market_open": {"icon": "📈", "header": "🟢"},
            "market_closed": {"icon": "📉", "header": "⚪"},
            "auth": {"icon": "🔑", "header": "🔐"},
            "alert": {"icon": "🔔", "header": "🚨"},
        }
        
        # Default to info if invalid status
        format_data = status_formats.get(status.lower(), status_formats["info"])
        
        # Current timestamp
        import pytz
        
        timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Create a well-formatted message with a border
        formatted_msg = (
            f"{format_data['header']} <b>{title}</b> {format_data['icon']}\n\n"
            f"{message}\n\n"
            f"<i>📆 {timestamp}</i>\n"
            f"<code>Kite Trading Bot</code>"
        )
        
        try:
            self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=formatted_msg,
                parse_mode="HTML",
                disable_notification=disable_notification
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to send formatted Telegram message: {str(e)}")
            # Fallback to simple message if HTML formatting fails
            try:
                simple_msg = f"{title}\n\n{message}\n\nTime: {timestamp}"
                self.bot.send_message(
                    chat_id=self.telegram_chat_id,
                    text=simple_msg,
                    disable_notification=disable_notification
                )
                return True
            except:
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
            
            return self.send_formatted_notification("ChartInk Alert", message)
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
            
            # Calculate trade value
            trade_value = quantity * price
            
            # Create the message
            message = f"{emoji} <b>{transaction_type.upper()} Order Placed</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Quantity:</b> {quantity}\n"
            message += f"<b>Price:</b> ₹{price}\n"
            message += f"<b>Value:</b> ₹{trade_value:.2f}\n"
            message += f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"<b>Order ID:</b> <code>{order_id}</code>\n"
            
            return self.send_formatted_notification("Trade Notification", message)
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
            
            return self.send_formatted_notification("Authentication Status", message)
        except Exception as e:
            self.logger.error(f"Failed to create auth status notification: {e}")
            return False
    
    def notify_day_summary(self, trades_data, pnl_data=None):
        """
        Send a notification with daily trading summary and P&L information based on positions data.
        
        Args:
            trades_data (list): List of position details from Kite API.
            pnl_data (dict): Dictionary with P&L information, if available.
        
        Returns:
            bool: True if the notification was sent successfully, False otherwise.
        """
        try:
            if not trades_data:
                message = f"📊 <b>Portfolio Summary</b> - {date.today().strftime('%d %b %Y')}\n\n"
                message += "No active positions found."
                return self.send_formatted_notification("Portfolio Summary", message)
            
            # Count positions by type
            mis_buy = sum(1 for t in trades_data if t.get('signal', '').upper() == 'BUY' and t.get('product') == 'MIS')
            mis_sell = sum(1 for t in trades_data if t.get('signal', '').upper() == 'SELL' and t.get('product') == 'MIS')
            cnc_buy = sum(1 for t in trades_data if t.get('signal', '').upper() == 'BUY' and t.get('product') == 'CNC')
            cnc_sell = sum(1 for t in trades_data if t.get('signal', '').upper() == 'SELL' and t.get('product') == 'CNC')
            
            # Calculate total value by type
            mis_buy_value = sum(t.get('value', 0) for t in trades_data if t.get('signal', '').upper() == 'BUY' and t.get('product') == 'MIS')
            mis_sell_value = sum(t.get('value', 0) for t in trades_data if t.get('signal', '').upper() == 'SELL' and t.get('product') == 'MIS')
            cnc_buy_value = sum(t.get('value', 0) for t in trades_data if t.get('signal', '').upper() == 'BUY' and t.get('product') == 'CNC')
            cnc_sell_value = sum(t.get('value', 0) for t in trades_data if t.get('signal', '').upper() == 'SELL' and t.get('product') == 'CNC')
            
            # Calculate total P&L
            total_pnl = sum(t.get('pnl', 0) for t in trades_data)
            winning_trades = sum(1 for t in trades_data if t.get('pnl', 0) > 0)
            losing_trades = sum(1 for t in trades_data if t.get('pnl', 0) < 0)
            
            # Construct message
            message = f"📊 <b>Portfolio Summary</b> - {date.today().strftime('%d %b %Y')}\n\n"
            
            # P&L Summary
            pnl_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
            message += f"<b>P&L Summary:</b>\n"
            message += f"{pnl_emoji} Total P&L: ₹{total_pnl:.2f}\n"
            message += f"✅ Winning: {winning_trades} | ❌ Losing: {losing_trades}\n\n"
            
            # Position Summary
            message += "<b>Position Summary:</b>\n"
            if mis_buy or mis_sell:
                message += "🔄 <b>Intraday (MIS):</b>\n"
                if mis_buy:
                    message += f"  • Long: {mis_buy} positions (₹{mis_buy_value:.2f})\n"
                if mis_sell:
                    message += f"  • Short: {mis_sell} positions (₹{mis_sell_value:.2f})\n"
            
            if cnc_buy or cnc_sell:
                message += "📅 <b>Delivery (CNC):</b>\n"
                if cnc_buy:
                    message += f"  • Long: {cnc_buy} positions (₹{cnc_buy_value:.2f})\n"
                if cnc_sell:
                    message += f"  • Short: {cnc_sell} positions (₹{cnc_sell_value:.2f})\n"
            message += "\n"
            
            # List of all positions with P&L
            message += "<b>Current Positions:</b>\n"
            positions_to_show = trades_data[:10]  # Show only first 10 positions
            
            for position in positions_to_show:
                symbol = position.get('stock', 'Unknown')
                action = position.get('signal', 'Unknown').upper()
                quantity = position.get('quantity', 0)
                price = position.get('price', 0)
                value = position.get('value', 0)
                product = position.get('product', 'Unknown')
                trade_pnl = position.get('pnl', 0)
                
                # Emojis based on position type and direction
                type_emoji = "🔄" if product == "MIS" else "📅"
                dir_emoji = "🟢" if action == "BUY" else "🔴"
                
                pnl_str = ""
                if trade_pnl != 0:
                    pnl_emoji = "📈" if trade_pnl > 0 else "📉"
                    pnl_str = f" | {pnl_emoji} ₹{trade_pnl:.2f}"
                
                message += f"{type_emoji} {dir_emoji} {symbol}: {action} {quantity} @ ₹{price:.2f} ({product}){pnl_str}\n"
            
            if len(trades_data) > 10:
                message += f"\n... and {len(trades_data) - 10} more positions"
            
            return self.send_formatted_notification("Portfolio Summary", message)
        except Exception as e:
            self.logger.error(f"Error sending day summary notification: {e}")
            return False
    
    def send_test_message(self):
        """Send a test message to verify Telegram configuration"""
        test_message = "🧪 <b>Test Message</b>\n\nThis is a test message from your trading application to verify Telegram notifications are working correctly."
        return self.send_formatted_notification("Test Message", test_message)

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the notification
    notifier = TelegramNotifier()
    notifier.send_test_message() 