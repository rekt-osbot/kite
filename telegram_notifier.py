import os
import logging
import json
import requests
from datetime import datetime, date
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
                return self.send_message(message)
            
            # Count buy and sell positions
            buy_count = sum(1 for trade in trades_data if trade.get('signal', '').upper() == 'BUY')
            sell_count = sum(1 for trade in trades_data if trade.get('signal', '').upper() == 'SELL')
            
            # Calculate total value of buy and sell positions
            buy_value = sum(trade.get('value', 0) for trade in trades_data if trade.get('signal', '').upper() == 'BUY')
            sell_value = sum(trade.get('value', 0) for trade in trades_data if trade.get('signal', '').upper() == 'SELL')
            
            # Group positions by scanner/alert
            scanners = {}
            for trade in trades_data:
                scanner = trade.get('scanner', 'Unknown')
                if scanner not in scanners:
                    scanners[scanner] = {
                        'count': 0,
                        'buy_count': 0,
                        'sell_count': 0
                    }
                scanners[scanner]['count'] += 1
                if trade.get('signal', '').upper() == 'BUY':
                    scanners[scanner]['buy_count'] += 1
                elif trade.get('signal', '').upper() == 'SELL':
                    scanners[scanner]['sell_count'] += 1
            
            # Create the message
            message = f"📊 <b>Portfolio Summary</b> - {date.today().strftime('%d %b %Y')}\n\n"
            
            # Add P&L summary if available
            if pnl_data:
                pnl_amount = pnl_data.get('total_pnl', 0)
                pnl_percent = pnl_data.get('total_pnl_percent', 0)
                winning_trades = pnl_data.get('winning_trades', 0)
                losing_trades = pnl_data.get('losing_trades', 0)
                
                # Determine emoji based on P&L
                if pnl_amount > 0:
                    pnl_emoji = "🟢📈"
                elif pnl_amount < 0:
                    pnl_emoji = "🔴📉"
                else:
                    pnl_emoji = "⚪️"
                
                message += f"<b>Portfolio P&L:</b> {pnl_emoji} ₹{pnl_amount:.2f} ({pnl_percent:.2f}%)\n"
                message += f"<b>Win/Loss:</b> {winning_trades}/{losing_trades}\n\n"
            
            # Position count summary
            message += f"<b>Total Positions:</b> {len(trades_data)}\n"
            message += f"<b>Long Positions:</b> {buy_count} (₹{buy_value:.2f})\n"
            message += f"<b>Short Positions:</b> {sell_count} (₹{sell_value:.2f})\n\n"
            
            # Scanner summary
            if len(scanners) > 1:  # Only show if there's more than one scanner
                message += "<b>Scanner Stats:</b>\n"
                for scanner, stats in scanners.items():
                    message += f"- <b>{scanner}</b>: {stats['count']} positions ({stats['buy_count']} long, {stats['sell_count']} short)\n"
                message += "\n"
            
            # List of all positions with P&L
            message += "<b>Current Positions:</b>\n"
            positions_to_show = trades_data[:10]  # Show only the first 10 positions to avoid message length limits
            
            # Add P&L data to positions if available
            if pnl_data and 'trades_detail' in pnl_data:
                # Create a mapping of symbol to P&L data for quick lookup
                pnl_map = {}
                for trade_detail in pnl_data['trades_detail']:
                    key = f"{trade_detail.get('symbol')}_{trade_detail.get('action')}"
                    pnl_map[key] = trade_detail
                
                # Display positions with P&L info
                for position in positions_to_show:
                    symbol = position.get('stock', 'Unknown')
                    action = position.get('signal', 'Unknown').upper()
                    quantity = position.get('quantity', 0)
                    price = position.get('price', 0)
                    value = position.get('value', 0)
                    
                    # Get P&L info directly from position
                    trade_pnl = position.get('pnl', 0)
                    
                    emoji = "🟢" if action == "BUY" else "🔴"
                    pnl_str = ""
                    if trade_pnl != 0:
                        pnl_emoji = "📈" if trade_pnl > 0 else "📉"
                        pnl_str = f" | {pnl_emoji} ₹{trade_pnl:.2f}"
                    
                    message += f"{emoji} {symbol}: {action} {quantity} @ ₹{price:.2f} (₹{value:.2f}){pnl_str}\n"
            else:
                # Display positions without P&L info
                for position in positions_to_show:
                    symbol = position.get('stock', 'Unknown')
                    action = position.get('signal', 'Unknown').upper()
                    quantity = position.get('quantity', 0)
                    price = position.get('price', 0)
                    value = position.get('value', 0)
                    
                    emoji = "🟢" if action == "BUY" else "🔴"
                    message += f"{emoji} {symbol}: {action} {quantity} @ ₹{price:.2f} (₹{value:.2f})\n"
            
            if len(trades_data) > 10:
                message += f"...and {len(trades_data) - 10} more positions\n"
            
            return self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to create day summary notification: {e}")
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