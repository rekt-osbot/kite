import json
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, redirect, send_from_directory
from dotenv import load_dotenv
from kite_connect import KiteConnect
from scheduler import start_scheduler
from telegram_notifier import TelegramNotifier

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize Kite Connect
kite = KiteConnect()

# Initialize Telegram notifier
telegram = TelegramNotifier()

# Trading configuration
DEFAULT_QUANTITY = int(os.getenv("DEFAULT_QUANTITY", 1))
MAX_TRADE_VALUE = float(os.getenv("MAX_TRADE_VALUE", 5000))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", 2))
TARGET_PERCENT = float(os.getenv("TARGET_PERCENT", 4))

# Store received alerts in memory (cleared on restart)
# In production, consider using a database
received_alerts = []

# Authentication routes
@app.route('/')
def index():
    """Dashboard page"""
    return send_from_directory('auth', 'dashboard.html')

@app.route('/auth/refresh')
def auth_refresh():
    """Show the token refresh page"""
    return send_from_directory('auth', 'refresh.html')

@app.route('/auth/alerts')
def alerts_page():
    """Show the alerts page"""
    return send_from_directory('auth', 'alerts.html')

@app.route('/auth/settings')
def settings_page():
    """Show the settings page"""
    return send_from_directory('auth', 'settings.html')

@app.route('/auth/login')
def auth_login():
    """Start the Zerodha login flow"""
    login_url = kite.get_login_url()
    return redirect(login_url)

@app.route('/auth/redirect')
def auth_redirect():
    """Handle redirect from Zerodha after login"""
    request_token = request.args.get('request_token')
    if not request_token:
        return jsonify({"status": "error", "message": "No request token received"}), 400
    
    try:
        # Generate session from the request token
        kite.generate_session(request_token)
        
        # Notify via Telegram if enabled
        try:
            profile = kite.get_profile()
            telegram.notify_auth_status(True, profile.get('user_name', 'Unknown'))
        except:
            pass
            
        return redirect('/auth/refresh')
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/auth/status')
def auth_status():
    """Check if authenticated with Kite"""
    try:
        profile = kite.get_profile()
        return jsonify({
            "status": "success", 
            "authenticated": True, 
            "user": profile['user_name'],
            "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except:
        return jsonify({"status": "error", "authenticated": False})

def authenticate_kite():
    """Ensure Kite API is authenticated"""
    try:
        kite.get_profile()
        logger.info("Kite API already authenticated")
        return True
    except Exception as e:
        logger.error(f"Kite authentication error: {e}")
        # For Railway deployment, we can't automatically login
        # since it requires user interaction
        return False

def place_order(symbol, transaction_type, quantity, order_type="MARKET", price=0):
    """Place an order via Kite Connect"""
    try:
        exchange = "NSE"
        if "NFO:" in symbol:
            exchange = "NFO"
            symbol = symbol.replace("NFO:", "")
        elif "NSE:" in symbol:
            symbol = symbol.replace("NSE:", "")
        
        # Place the order
        order_params = {
            "tradingsymbol": symbol,
            "exchange": exchange,
            "transaction_type": transaction_type,  # BUY or SELL
            "quantity": quantity,
            "order_type": order_type,  # MARKET, LIMIT, etc.
            "product": "MIS"  # MIS, CNC, etc.
        }
        
        # Add price for LIMIT orders
        if order_type == "LIMIT" and price > 0:
            order_params["price"] = price
        
        # Add trigger price for SL orders
        if order_type == "SL" and price > 0:
            order_params["price"] = price
            # Set trigger price slightly below for buy SL and slightly above for sell SL
            trigger_offset = 0.05 * price
            if transaction_type == "BUY":
                order_params["trigger_price"] = round(price - trigger_offset, 1)
            else:
                order_params["trigger_price"] = round(price + trigger_offset, 1)
        
        order_id = kite.place_order(
            variety="regular",
            params=order_params
        )
        
        logger.info(f"Order placed successfully. Order ID: {order_id}")
        return order_id
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return None

def process_chartink_alert(alert_data):
    """
    Process the ChartInk scanner alert.
    ChartInk sends data in the following format:
    {
        "stocks": "STOCK1,STOCK2,STOCK3",
        "trigger_prices": "100.5,200.5,300.5",
        "triggered_at": "2:34 pm",
        "scan_name": "Short term breakouts",
        "scan_url": "short-term-breakouts",
        "alert_name": "Alert for Short term breakouts"
    }
    """
    try:
        # Add timestamp to the alert data
        alert_data["timestamp"] = datetime.now().isoformat()
        
        # Store the alert
        received_alerts.append(alert_data)
        
        # Notify via Telegram
        telegram.notify_chartink_alert(alert_data)
        
        # Extract data from the alert
        stocks = alert_data.get('stocks', '').split(',')
        prices = alert_data.get('trigger_prices', '').split(',')
        triggered_at = alert_data.get('triggered_at', '')
        scan_name = alert_data.get('scan_name', '')
        scan_url = alert_data.get('scan_url', '')
        alert_name = alert_data.get('alert_name', '')
        
        logger.info(f"Received alert from scanner '{scan_name}' at {triggered_at}")
        logger.info(f"Stocks: {stocks}")
        logger.info(f"Prices: {prices}")
        
        # Validate required data
        if not stocks or not prices or len(stocks) != len(prices):
            logger.error(f"Invalid alert data: {alert_data}")
            return False
        
        success_count = 0
        error_count = 0
        
        # Process each stock in the alert
        for i, stock in enumerate(stocks):
            stock = stock.strip()
            if not stock:
                continue
                
            try:
                price = float(prices[i].strip())
                
                # Determine transaction type based on scan name
                # Assuming "breakout" or "buy" in scan name means BUY, otherwise SELL
                scan_lower = scan_name.lower()
                transaction_type = "BUY"
                if "sell" in scan_lower or "short" in scan_lower or "bearish" in scan_lower:
                    transaction_type = "SELL"
                
                logger.info(f"Processing {stock} with {transaction_type} at price {price}")
                
                # Calculate quantity based on price and max trade value
                quantity = min(DEFAULT_QUANTITY, int(MAX_TRADE_VALUE / price))
                if quantity <= 0:
                    quantity = 1
                
                # Prepend NSE: to stock if not already present
                if not (stock.startswith("NSE:") or stock.startswith("NFO:")):
                    stock = f"NSE:{stock}"
                
                # Place the order
                order_id = place_order(stock, transaction_type, quantity)
                if not order_id:
                    logger.error(f"Failed to place order for {stock}")
                    error_count += 1
                    continue
                
                # If it's a BUY order, place a corresponding stop-loss and target
                if transaction_type == "BUY":
                    # Calculate stop-loss and target prices
                    stop_loss_price = round(price * (1 - STOP_LOSS_PERCENT/100), 1)
                    target_price = round(price * (1 + TARGET_PERCENT/100), 1)
                    
                    # Place stop-loss order
                    sl_order_id = place_order(
                        stock, 
                        "SELL", 
                        quantity, 
                        order_type="SL", 
                        price=stop_loss_price
                    )
                    
                    # Place target order (limit sell)
                    target_order_id = place_order(
                        stock, 
                        "SELL", 
                        quantity, 
                        order_type="LIMIT", 
                        price=target_price
                    )
                    
                    logger.info(f"Placed SL order: {sl_order_id} and Target order: {target_order_id} for {stock}")
                
                # Log the trade details
                trade_details = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "stock": stock,
                    "signal": transaction_type,
                    "price": price,
                    "quantity": quantity,
                    "scanner": scan_name,
                    "order_id": order_id
                }
                
                # Send trade notification to Telegram
                telegram.notify_trade(trade_details)
                
                # Append to trade log file
                with open("trade_log.json", "a") as f:
                    f.write(json.dumps(trade_details) + "\n")
                
                success_count += 1
                logger.info(f"Successfully processed {stock}")
                
            except Exception as e:
                logger.error(f"Error processing stock {stock}: {e}")
                error_count += 1
        
        logger.info(f"Alert processing complete. Success: {success_count}, Errors: {error_count}")
        return success_count > 0
    
    except Exception as e:
        logger.error(f"Error processing alert: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from ChartInk"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        data = request.json
        logger.info(f"Received webhook data: {data}")
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # Process the alert
        success = process_chartink_alert(data)
        
        if success:
            return jsonify({"status": "success", "message": "Alert processed successfully"}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to process alert"}), 500
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# API Endpoints for Dashboard and Settings Pages
@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get current positions"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        positions = kite.get_positions()
        return jsonify({"status": "success", "data": positions})
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Get today's orders"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        orders = kite.get_orders()
        return jsonify({"status": "success", "data": orders})
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/margins', methods=['GET'])
def get_margins():
    """Get available margins"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        margins = kite.get_margins()
        return jsonify({"status": "success", "data": margins})
    except Exception as e:
        logger.error(f"Error getting margins: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get received alerts"""
    try:
        # Only return alerts from today
        today = datetime.now().date()
        today_alerts = [
            alert for alert in received_alerts 
            if datetime.fromisoformat(alert.get("timestamp", "")).date() == today
        ]
        
        return jsonify({"status": "success", "data": today_alerts})
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings"""
    try:
        settings = {
            "DEFAULT_QUANTITY": DEFAULT_QUANTITY,
            "MAX_TRADE_VALUE": MAX_TRADE_VALUE,
            "STOP_LOSS_PERCENT": STOP_LOSS_PERCENT,
            "TARGET_PERCENT": TARGET_PERCENT,
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", "")
        }
        
        return jsonify({"status": "success", "data": settings})
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def update_env_value(key, value):
    """
    Update a value in the .env file
    Note: This only works locally, not on Railway
    """
    if os.path.exists('.env'):
        try:
            with open('.env', 'r') as f:
                lines = f.readlines()
            
            updated = False
            with open('.env', 'w') as f:
                for line in lines:
                    if line.startswith(f"{key}="):
                        f.write(f"{key}={value}\n")
                        updated = True
                    else:
                        f.write(line)
                
                if not updated:
                    f.write(f"{key}={value}\n")
            
            # Also update the environment variable in memory
            os.environ[key] = str(value)
            return True
        except Exception as e:
            logger.error(f"Error updating .env file: {e}")
            return False
    else:
        # For Railway we can only update in memory
        os.environ[key] = str(value)
        return True

@app.route('/api/settings/trading', methods=['POST'])
def update_trading_settings():
    """Update trading settings"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        data = request.json
        
        # Update global variables
        global DEFAULT_QUANTITY, MAX_TRADE_VALUE, STOP_LOSS_PERCENT, TARGET_PERCENT
        
        DEFAULT_QUANTITY = int(data.get("DEFAULT_QUANTITY", DEFAULT_QUANTITY))
        MAX_TRADE_VALUE = float(data.get("MAX_TRADE_VALUE", MAX_TRADE_VALUE))
        STOP_LOSS_PERCENT = float(data.get("STOP_LOSS_PERCENT", STOP_LOSS_PERCENT))
        TARGET_PERCENT = float(data.get("TARGET_PERCENT", TARGET_PERCENT))
        
        # Update .env file if it exists
        update_env_value("DEFAULT_QUANTITY", DEFAULT_QUANTITY)
        update_env_value("MAX_TRADE_VALUE", MAX_TRADE_VALUE)
        update_env_value("STOP_LOSS_PERCENT", STOP_LOSS_PERCENT)
        update_env_value("TARGET_PERCENT", TARGET_PERCENT)
        
        logger.info(f"Trading settings updated: DEFAULT_QUANTITY={DEFAULT_QUANTITY}, MAX_TRADE_VALUE={MAX_TRADE_VALUE}, STOP_LOSS_PERCENT={STOP_LOSS_PERCENT}, TARGET_PERCENT={TARGET_PERCENT}")
        
        return jsonify({"status": "success", "message": "Trading settings updated successfully"})
    except Exception as e:
        logger.error(f"Error updating trading settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings/telegram', methods=['POST'])
def update_telegram_settings():
    """Update Telegram settings"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Kite authentication failed"}), 500
    
    try:
        data = request.json
        
        bot_token = data.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = data.get("TELEGRAM_CHAT_ID", "")
        
        # Update .env file if it exists
        update_env_value("TELEGRAM_BOT_TOKEN", bot_token)
        update_env_value("TELEGRAM_CHAT_ID", chat_id)
        
        # Update the telegram notifier
        global telegram
        telegram = TelegramNotifier(bot_token, chat_id)
        
        logger.info(f"Telegram settings updated: BOT_TOKEN={'*'*10 if bot_token else 'Not set'}, CHAT_ID={chat_id}")
        
        return jsonify({"status": "success", "message": "Telegram settings updated successfully"})
    except Exception as e:
        logger.error(f"Error updating Telegram settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    """Send a test message via Telegram"""
    try:
        data = request.json
        
        bot_token = data.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = data.get("TELEGRAM_CHAT_ID", "")
        
        test_notifier = TelegramNotifier(bot_token, chat_id)
        
        if not test_notifier.is_enabled():
            return jsonify({"status": "error", "message": "Please provide both Bot Token and Chat ID"}), 400
        
        result = test_notifier.send_test_message()
        
        if result:
            return jsonify({"status": "success", "message": "Test message sent successfully"})
        else:
            return jsonify({"status": "error", "message": "Failed to send test message. Check your credentials and network connection."}), 500
    except Exception as e:
        logger.error(f"Error sending test Telegram message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    # Attempt to authenticate to check if token is valid
    authenticate_kite()
    
    # Start the auth checker scheduler
    start_scheduler()
    
    logger.info(f"Starting webhook server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug) 