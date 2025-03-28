import json
import os
import logging
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect, send_from_directory
from dotenv import load_dotenv
from kite_connect import KiteConnect
from scheduler import start_scheduler
from telegram_notifier import TelegramNotifier
from models import db, User, AuthToken, Settings

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

# Database configuration
database_url = os.getenv('DATABASE_URL')
if not database_url:
    # Local development fallback
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kite.db'
else:
    # Ensure DATABASE_URL is compatible with SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Initialize Kite Connect
kite = KiteConnect()

# Initialize Telegram notifier
telegram = TelegramNotifier()

# Trading configuration - load from environment or database
def load_trading_config():
    """Load trading configuration from database if available, otherwise from environment"""
    with app.app_context():
        default_quantity = Settings.get_value('DEFAULT_QUANTITY', os.getenv("DEFAULT_QUANTITY", "1"))
        max_trade_value = Settings.get_value('MAX_TRADE_VALUE', os.getenv("MAX_TRADE_VALUE", "5000"))
        stop_loss_percent = Settings.get_value('STOP_LOSS_PERCENT', os.getenv("STOP_LOSS_PERCENT", "2"))
        target_percent = Settings.get_value('TARGET_PERCENT', os.getenv("TARGET_PERCENT", "4"))
        max_position_size = Settings.get_value('MAX_POSITION_SIZE', os.getenv("MAX_POSITION_SIZE", "5000"))
        
        return {
            'DEFAULT_QUANTITY': int(default_quantity),
            'MAX_TRADE_VALUE': float(max_trade_value),
            'STOP_LOSS_PERCENT': float(stop_loss_percent),
            'TARGET_PERCENT': float(target_percent),
            'MAX_POSITION_SIZE': float(max_position_size)
        }

# Initialize trading configuration
config = load_trading_config()
DEFAULT_QUANTITY = config['DEFAULT_QUANTITY']
MAX_TRADE_VALUE = config['MAX_TRADE_VALUE']
STOP_LOSS_PERCENT = config['STOP_LOSS_PERCENT']
TARGET_PERCENT = config['TARGET_PERCENT']
MAX_POSITION_SIZE = config['MAX_POSITION_SIZE']

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
        session_data = kite.generate_session(request_token)
        
        # Get user profile
        try:
            profile = kite.get_profile()
            user_id = profile.get('user_id')
            username = profile.get('user_name')
            email = profile.get('email')
            
            # Store user and token in database
            with app.app_context():
                # Check if user already exists
                user = User.query.filter_by(user_id=user_id).first()
                if not user:
                    # Create new user
                    user = User(user_id=user_id, username=username, email=email)
                    db.session.add(user)
                    db.session.commit()
                
                # Delete any existing tokens for this user
                AuthToken.query.filter_by(user_id=user.id).delete()
                
                # Create new token with 24 hour expiration
                token = AuthToken.create_token(
                    user.id, 
                    session_data.get("access_token"),
                    expires_in_hours=24
                )
                
                db.session.add(token)
                db.session.commit()
                
                # Set the token in KiteConnect instance
                kite.set_access_token(token.access_token)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")
        
        # Notify via Telegram if enabled
        try:
            telegram.notify_auth_status(True, profile.get('user_name', 'Unknown'))
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            
        return redirect('/auth/refresh')
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/auth/status')
def auth_status():
    """Check if authenticated with Kite"""
    try:
        with app.app_context():
            # Find the most recent valid token
            token = AuthToken.query.order_by(AuthToken.created_at.desc()).first()
            
            if token and not token.is_expired:
                # Valid token found, get user info
                user = User.query.get(token.user_id)
                
                # Set token in KiteConnect instance if needed
                if kite.access_token != token.access_token:
                    kite.set_access_token(token.access_token)
                
                # Calculate expiration time
                expiry_time = token.expires_at
                
                return jsonify({
                    "status": "success", 
                    "authenticated": True, 
                    "user": user.username,
                    "last_login": token.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "expires_at": expiry_time.strftime("%Y-%m-%dT%H:%M:%S")
                })
            
            # No valid token found
            return jsonify({"status": "error", "authenticated": False})
    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        return jsonify({"status": "error", "authenticated": False, "message": str(e)})

def authenticate_kite():
    """Ensure Kite API is authenticated using stored token when possible"""
    try:
        with app.app_context():
            # Find the most recent valid token
            token = AuthToken.query.order_by(AuthToken.created_at.desc()).first()
            
            if token and not token.is_expired:
                # Valid token found, set in KiteConnect instance
                if kite.access_token != token.access_token:
                    kite.set_access_token(token.access_token)
                
                # Get user info
                user = User.query.get(token.user_id)
                logger.info(f"Kite API authenticated as {user.username}")
                return True
            
            # No valid token found
            return False
    except Exception as e:
        logger.error(f"Kite authentication error: {e}")
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
            "product": "CNC"  # Using CNC (delivery) instead of MIS (intraday)
        }
        
        # Add price for LIMIT orders
        if order_type == "LIMIT" and price > 0:
            order_params["price"] = price
        
        # Add trigger price for SL orders with proper range
        if order_type == "SL" and price > 0:
            # Calculate permissible range based on exchange requirements
            # For NSE equity, typically 3% for most stocks
            if transaction_type == "SELL":
                # For stop-loss sell orders, trigger price should be lower
                trigger_price = round(price * 0.97, 1)  # 3% below limit price
                order_params["trigger_price"] = trigger_price
                # Limit price should be slightly below trigger price to ensure execution
                order_params["price"] = round(trigger_price * 0.99, 1)
                logger.info(f"SL SELL order configured - Trigger price: {trigger_price}, Limit price: {order_params['price']}")
            else:
                # For stop-loss buy orders, trigger price should be higher
                trigger_price = round(price * 1.03, 1)  # 3% above limit price
                order_params["trigger_price"] = trigger_price
                # Limit price should be slightly above trigger price
                order_params["price"] = round(trigger_price * 1.01, 1)
                logger.info(f"SL BUY order configured - Trigger price: {trigger_price}, Limit price: {order_params['price']}")
        
        logger.info(f"Placing order: {json.dumps(order_params)}")
        
        order_id = kite.place_order(
            variety="regular",
            params=order_params
        )
        
        logger.info(f"Order placed successfully. Order ID: {order_id}")
        return order_id
    except Exception as e:
        logger.error(f"Order placement failed: {e}")
        return None

def process_chartink_alert(data):
    """Process the ChartInk alert data and place orders if appropriate"""
    logger.info(f"Processing ChartInk alert: {json.dumps(data)}")
    
    # Check if authentication is valid
    if not authenticate_kite():
        logger.error("Kite authentication failed, cannot process alert")
        return False
    
    # Get available funds first
    try:
        margins = kite.get_margins()
        available_funds = margins.get('equity', {}).get('available', {}).get('cash', 0)
        logger.info(f"Available funds: ₹{available_funds}")
        
        if available_funds <= 0:
            logger.error(f"Insufficient funds available (₹{available_funds}), cannot place orders")
            telegram.send_message(f"⚠️ <b>Alert Received but Insufficient Funds</b>\nAvailable: ₹{available_funds}")
            return False
    except Exception as e:
        logger.error(f"Error checking available funds: {e}")
        # Continue with the process but log the error
    
    # Extract alert data
    alert_name = data.get('alert_name', 'Unknown Alert')
    scan_name = data.get('scan_name', 'Unknown Scanner')
    stocks = data.get('stocks', [])
    
    # Handle both string and list formats for stocks
    if isinstance(stocks, str):
        stocks = [s.strip() for s in stocks.split(',') if s.strip()]
    
    # Get trigger prices (if available)
    prices = data.get('trigger_prices', [])
    if isinstance(prices, str):
        prices = [p.strip() for p in prices.split(',') if p.strip()]
    
    # Ensure we have the same number of prices as stocks
    while len(prices) < len(stocks):
        prices.append("N/A")
    
    # Determine the action (BUY/SELL) based on the scan name
    action = "BUY"  # Default
    if any(term in scan_name.lower() for term in ["sell", "short", "bearish", "breakdown", "down"]):
        action = "SELL"
    
    # Notify via Telegram
    try:
        telegram.notify_chartink_alert(scan_name, stocks, prices)
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
    
    # Store alert in memory
    alert_data = {
        'scan_name': scan_name,
        'scan_url': data.get('scan_url', ''),
        'alert_name': alert_name,
        'stocks': stocks,
        'prices': prices,
        'triggered_at': data.get('triggered_at', ''),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Add action to the stored alert
    alert_data['action'] = action
    received_alerts.append(alert_data)
    
    # Log alert info
    logger.info(f"Received alert from scanner '{scan_name}' at {alert_data['triggered_at']}")
    logger.info(f"Stocks: {stocks}")
    logger.info(f"Prices: {prices}")
    
    # Validate required data
    if not stocks or not prices or len(stocks) != len(prices):
        logger.error(f"Invalid alert data: {data}")
        return False
    
    success_count = 0
    error_count = 0
    funds_used = 0
    
    # Process each stock in the alert
    for i, stock in enumerate(stocks):
        stock = stock.strip()
        if not stock:
            continue
            
        try:
            price = float(prices[i].strip())
            
            logger.info(f"Processing {stock} with {action} at price {price}")
            
            # Check if we have enough funds remaining (considering what we've already allocated)
            remaining_funds = available_funds - funds_used
            if remaining_funds < price:
                logger.warning(f"Not enough remaining funds (₹{remaining_funds}) to place order for {stock} at ₹{price}")
                continue
            
            # Position sizing: Calculate quantity based on max position size per trade
            # Ensure it doesn't exceed available funds and follows max position size rule
            max_position_value = min(MAX_POSITION_SIZE, remaining_funds)
            quantity = int(max_position_value / price)
            
            # Fallback to default quantity if calculation fails or results in zero
            if quantity <= 0:
                quantity = DEFAULT_QUANTITY
                logger.warning(f"Using default quantity ({DEFAULT_QUANTITY}) for {stock}")
            
            # Log the position sizing calculation
            logger.info(f"Position sizing for {stock}: Max position size = ₹{MAX_POSITION_SIZE}, " +
                        f"Price = ₹{price}, Calculated quantity = {quantity}")
            
            # Prepend NSE: to stock if not already present
            if not (stock.startswith("NSE:") or stock.startswith("NFO:")):
                stock = f"NSE:{stock}"
            
            # Place the order
            order_id = place_order(stock, action, quantity)
            if not order_id:
                logger.error(f"Failed to place order for {stock}")
                error_count += 1
                continue
            
            # Track funds used
            funds_used += (price * quantity)
            logger.info(f"Allocated ₹{price * quantity:.2f} for {stock}, total allocated: ₹{funds_used:.2f}")
            
            # If it's a BUY order, place a corresponding stop-loss
            if action == "BUY":
                # Calculate stop-loss price
                stop_loss_price = round(price * (1 - STOP_LOSS_PERCENT/100), 1)
                
                # Place stop-loss order
                sl_order_id = place_order(
                    stock, 
                    "SELL", 
                    quantity, 
                    order_type="SL", 
                    price=stop_loss_price
                )
                
                logger.info(f"Placed SL order: {sl_order_id} for {stock}")
            
            # Log the trade details
            trade_details = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stock": stock,
                "signal": action,
                "price": price,
                "quantity": quantity,
                "value": price * quantity,
                "scanner": scan_name,
                "order_id": order_id
            }
            
            # Send trade notification to Telegram
            telegram.notify_trade(action, stock, quantity, price, order_id)
            
            # Append to trade log file (use a path that's writable in Railway)
            try:
                log_dir = os.path.join(os.getcwd(), 'logs')
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, "trade_log.json")
                
                with open(log_file, "a") as f:
                    f.write(json.dumps(trade_details) + "\n")
            except Exception as e:
                logger.error(f"Error writing to trade log: {e}")
            
            success_count += 1
            logger.info(f"Successfully processed {stock}")
            
        except Exception as e:
            logger.error(f"Error processing stock {stock}: {e}")
            error_count += 1
    
    logger.info(f"Alert processing complete. Success: {success_count}, Errors: {error_count}, Total funds allocated: ₹{funds_used:.2f}")
    return success_count > 0

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

# API endpoints
@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Not authenticated"})
    
    try:
        positions = kite.get_positions()
        return jsonify({"status": "success", "data": positions})
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/orders')
def get_orders():
    """Get today's orders"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Not authenticated"})
    
    try:
        orders = kite.get_orders()
        return jsonify({"status": "success", "data": orders})
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/margins')
def get_margins():
    """Get available margins"""
    if not authenticate_kite():
        return jsonify({"status": "error", "message": "Not authenticated"})
    
    try:
        margins = kite.get_margins()
        return jsonify({"status": "success", "data": margins})
    except Exception as e:
        logger.error(f"Error fetching margins: {e}")
        return jsonify({"status": "error", "message": str(e)})

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
    """Get application settings"""
    try:
        with app.app_context():
            settings = {
                'trading': {
                    'default_quantity': Settings.get_value('DEFAULT_QUANTITY', str(DEFAULT_QUANTITY)),
                    'max_trade_value': Settings.get_value('MAX_TRADE_VALUE', str(MAX_TRADE_VALUE)),
                    'stop_loss_percent': Settings.get_value('STOP_LOSS_PERCENT', str(STOP_LOSS_PERCENT)),
                    'target_percent': Settings.get_value('TARGET_PERCENT', str(TARGET_PERCENT)),
                    'max_position_size': Settings.get_value('MAX_POSITION_SIZE', str(MAX_POSITION_SIZE))
                },
                'telegram': {
                    'enabled': Settings.get_value('TELEGRAM_ENABLED', 'true'),
                    'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
                    'chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
                }
            }
            return jsonify({"status": "success", "settings": settings})
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings/trading', methods=['POST'])
def update_trading_settings():
    """Update trading settings"""
    try:
        # Declare globals at the beginning of the function
        global DEFAULT_QUANTITY, MAX_TRADE_VALUE, STOP_LOSS_PERCENT, TARGET_PERCENT, MAX_POSITION_SIZE
        
        data = request.json
        
        # Validate input data
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        # Extract settings
        default_quantity = data.get('default_quantity', DEFAULT_QUANTITY)
        max_trade_value = data.get('max_trade_value', MAX_TRADE_VALUE)
        stop_loss_percent = data.get('stop_loss_percent', STOP_LOSS_PERCENT)
        target_percent = data.get('target_percent', TARGET_PERCENT)
        max_position_size = data.get('max_position_size', MAX_POSITION_SIZE)
        
        # Validate settings
        try:
            default_quantity = int(default_quantity)
            max_trade_value = float(max_trade_value)
            stop_loss_percent = float(stop_loss_percent)
            target_percent = float(target_percent)
            max_position_size = float(max_position_size)
        except:
            return jsonify({"status": "error", "message": "Invalid setting values"}), 400
        
        # Update settings in database
        with app.app_context():
            Settings.set_value('DEFAULT_QUANTITY', str(default_quantity), 'Default quantity for orders')
            Settings.set_value('MAX_TRADE_VALUE', str(max_trade_value), 'Maximum trade value')
            Settings.set_value('STOP_LOSS_PERCENT', str(stop_loss_percent), 'Stop loss percentage')
            Settings.set_value('TARGET_PERCENT', str(target_percent), 'Target percentage')
            Settings.set_value('MAX_POSITION_SIZE', str(max_position_size), 'Maximum position size')
            db.session.commit()
        
        # Update global variables
        DEFAULT_QUANTITY = default_quantity
        MAX_TRADE_VALUE = max_trade_value
        STOP_LOSS_PERCENT = stop_loss_percent
        TARGET_PERCENT = target_percent
        MAX_POSITION_SIZE = max_position_size
        
        return jsonify({"status": "success", "message": "Trading settings updated"})
    except Exception as e:
        logger.error(f"Error updating trading settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings/telegram', methods=['POST'])
def update_telegram_settings():
    """Update Telegram notification settings"""
    try:
        data = request.json
        
        # Validate input data
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        # Extract settings
        enabled = data.get('enabled', True)
        bot_token = data.get('bot_token', os.getenv('TELEGRAM_BOT_TOKEN', ''))
        chat_id = data.get('chat_id', os.getenv('TELEGRAM_CHAT_ID', ''))
        
        # Update settings in database
        with app.app_context():
            Settings.set_value('TELEGRAM_ENABLED', str(enabled).lower(), 'Telegram notifications enabled')
            db.session.commit()
        
        # We don't store sensitive data like tokens in the database,
        # but we do update the environment variables in memory
        # Note: This won't persist across restarts on Railway
        if bot_token:
            os.environ['TELEGRAM_BOT_TOKEN'] = bot_token
        if chat_id:
            os.environ['TELEGRAM_CHAT_ID'] = chat_id
        
        # Update Telegram notifier
        telegram.update_config(bot_token, chat_id)
        
        return jsonify({"status": "success", "message": "Telegram settings updated"})
    except Exception as e:
        logger.error(f"Error updating telegram settings: {e}")
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