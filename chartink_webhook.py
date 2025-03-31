import json
import os
import logging
import time
import sys
import pytz
from datetime import datetime, timedelta, date
from flask import Flask, request, jsonify, redirect, send_from_directory, render_template_string
from dotenv import load_dotenv
from scheduler import start_scheduler, is_market_open, calculate_next_market_open
from nse_holidays import is_market_holiday, get_next_trading_day
from token_manager import token_manager
import memory_optimizer  # Import memory optimizer

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Market hours check - exit immediately if market is closed
# This will work regardless of how the app is started (gunicorn or directly)
BYPASS_MARKET_HOURS = os.getenv("BYPASS_MARKET_HOURS", "False").lower() == "true"

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Define a simple HTML template for market closed page
MARKET_CLOSED_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Closed - Kite Trading Bot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            text-align: center;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            background-color: #f9f9f9;
            margin-top: 40px;
        }
        h1 {
            color: #e67e22;
        }
        .time {
            font-size: 1.2em;
            margin: 20px 0;
        }
        .next {
            color: #16a085;
            font-weight: bold;
        }
        .reason {
            background-color: #f8edeb;
            padding: 10px;
            border-radius: 5px;
            border-left: 4px solid #e67e22;
            margin: 20px 0;
            text-align: left;
            font-weight: bold;
        }
        footer {
            margin-top: 40px;
            font-size: 0.8em;
            color: #777;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Market is Currently Closed</h1>
        <p>This trading bot only operates during market hours to optimize resource usage.</p>
        
        <div class="reason">
            <p>{{closure_reason}}</p>
        </div>
        
        <div class="time">
            <p>Current time: <strong>{{current_time}}</strong></p>
            <p class="next">Next market open: <strong>{{next_open_time}}</strong></p>
        </div>
        
        <div>
            <h3>Regular Market Hours:</h3>
            <p>Monday - Friday: 9:00 AM - 3:30 PM IST</p>
            <p>Weekends & Holidays: Closed</p>
        </div>
    </div>
    
    <footer>
        <p>Kite Trading Bot - Cost-optimized to run only during market hours</p>
        <p>For questions or support, please contact the administrator</p>
    </footer>
</body>
</html>
"""

def create_market_closed_app():
    """Create a Flask app that only shows a 'market closed' page with memory optimization"""
    closed_app = Flask(__name__)
    
    # Enable memory optimization for minimal app
    memory_optimizer.start_optimization()
    
    @closed_app.route('/', defaults={'path': ''})
    @closed_app.route('/<path:path>')
    def market_closed(path):
        now = datetime.now(IST)
        
        # Calculate next market open time
        next_market_open = calculate_next_market_open()
        
        # Get reason for market closure
        closure_reason = "Market is closed"
        if now.weekday() > 4:
            closure_reason = "Market is closed for the weekend"
        elif is_market_holiday(now.date()):
            # Get the holiday description
            from nse_holidays import fetch_nse_holidays
            holidays = fetch_nse_holidays()
            date_str = now.strftime('%Y-%m-%d')
            for holiday in holidays:
                if holiday.get('date') == date_str:
                    closure_reason = f"Market is closed for {holiday.get('description')}"
                    break
            
            # Clean up after use
            memory_optimizer.cleanup_modules(['nse_holidays'])
        else:
            # Must be outside trading hours
            closure_reason = "Market is closed outside trading hours"
        
        next_open_str = next_market_open.strftime('%Y-%m-%d %H:%M:%S IST') if next_market_open else "Unknown"
        current_time_str = now.strftime('%Y-%m-%d %H:%M:%S IST')
        
        return render_template_string(
            MARKET_CLOSED_HTML, 
            current_time=current_time_str,
            next_open_time=next_open_str,
            closure_reason=closure_reason
        )
    
    # Register shutdown function to stop optimization
    @closed_app.teardown_appcontext
    def shutdown_memory_optimizer(exception=None):
        memory_optimizer.stop_optimization()
    
    return closed_app

# Check if we should run the full app or just the market-closed version
if not BYPASS_MARKET_HOURS and not is_market_open():
    logger.info(f"Market is closed at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}. Serving market-closed page.")
    
    # Send Telegram notification about market closure if it's due to a holiday
    now = datetime.now(IST)
    if is_market_holiday(now.date()):
        # Import only what we need to avoid circular imports
        try:
            from telegram_notifier import TelegramNotifier
            from nse_holidays import fetch_nse_holidays
            
            # Initialize Telegram notifier
            telegram = TelegramNotifier()
            
            # Get holiday description
            holidays = fetch_nse_holidays()
            date_str = now.strftime('%Y-%m-%d')
            holiday_desc = "Holiday"
            for holiday in holidays:
                if holiday.get('date') == date_str:
                    holiday_desc = holiday.get('description', 'Holiday')
                    break
            
            # Calculate next market open
            next_market_open = calculate_next_market_open()
            next_open_str = next_market_open.strftime('%Y-%m-%d %H:%M:%S IST') if next_market_open else "Unknown"
            
            # Send notification
            message = f"🔴 <b>Market Closed: {holiday_desc}</b>\n\n" \
                    f"The trading bot has been shut down for today due to a market holiday.\n" \
                    f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S IST')}\n" \
                    f"Next market open: {next_open_str}\n\n" \
                    f"The bot will automatically restart when the market reopens."
            
            telegram.send_message(message)
            logger.info(f"Sent market holiday notification via Telegram: Market closed for {holiday_desc}")
            
            # Clean up modules to save memory
            memory_optimizer.cleanup_modules(['telegram_notifier', 'nse_holidays'])
        except Exception as e:
            logger.error(f"Failed to send market holiday notification: {e}")
    
    app = create_market_closed_app()
else:
    logger.info("Market is open or bypass enabled. Starting the full application...")
    
    # Start memory optimization in background
    memory_optimizer.start_optimization()
    
    # Only import required modules when the market is open
    from kite_connect import KiteConnect
    from kite_rate_limiter import get_rate_limited_kite  # Import the rate limiter
    from telegram_notifier import TelegramNotifier
    from apscheduler.schedulers.background import BackgroundScheduler
    from file_storage import storage
    
    # Initialize Flask app
    app = Flask(__name__)

    # Register token status endpoints
    try:
        from token_status import register_token_endpoints
        app = register_token_endpoints(app)
        logger.info("Registered token status endpoints")
    except Exception as e:
        logger.error(f"Failed to register token status endpoints: {e}")

    # Initialize Kite Connect with rate limiting
    kite_base = KiteConnect()
    kite = get_rate_limited_kite(kite_base)  # Apply rate limiting to the Kite instance

    # Initialize Telegram notifier
    telegram = TelegramNotifier()

    # Scheduler for periodic tasks
    scheduler = BackgroundScheduler()

    # Trading configuration - load from file storage
    def load_trading_config():
        """Load trading configuration from storage"""
        settings = storage.get_all_settings()
        
        # Use memory_optimizer to optimize the dictionary
        return memory_optimizer.optimize_dict({
            'DEFAULT_QUANTITY': int(settings.get('DEFAULT_QUANTITY', "1")),
            'MAX_TRADE_VALUE': float(settings.get('MAX_TRADE_VALUE', "5000")),
            'STOP_LOSS_PERCENT': float(settings.get('STOP_LOSS_PERCENT', "2")),
            'TARGET_PERCENT': float(settings.get('TARGET_PERCENT', "4")),
            'MAX_POSITION_SIZE': float(settings.get('MAX_POSITION_SIZE', "5000"))
        })

    # Initialize trading configuration
    config = load_trading_config()
    DEFAULT_QUANTITY = config['DEFAULT_QUANTITY']
    MAX_TRADE_VALUE = config['MAX_TRADE_VALUE']
    STOP_LOSS_PERCENT = config['STOP_LOSS_PERCENT']
    TARGET_PERCENT = config['TARGET_PERCENT']
    MAX_POSITION_SIZE = config.get('MAX_POSITION_SIZE', 5000)

    # Store received alerts in memory (cleared on restart)
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
                
                # Store token in file storage
                token_data = storage.save_token(
                    user_id,
                    username, 
                    session_data.get("access_token"),
                    expires_in_hours=24
                )
                
                # Set the token in KiteConnect instance
                kite.set_access_token(token_data['access_token'])
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
            # Get token from storage
            token_data = storage.get_token()
            
            if token_data:
                # Valid token found
                username = token_data.get('username', 'Unknown')
                created_at = token_data.get('created_at', '')
                expires_at = token_data.get('expires_at', '')
                
                # Set token in KiteConnect instance if needed
                if kite.access_token != token_data.get('access_token'):
                    kite.set_access_token(token_data.get('access_token'))
                
                return jsonify({
                    "status": "success", 
                    "authenticated": True, 
                    "user": username,
                    "last_login": created_at,
                    "expires_at": expires_at
                })
            
            # No valid token found
            return jsonify({"status": "error", "authenticated": False})
        except Exception as e:
            logger.error(f"Auth status check failed: {e}")
            return jsonify({"status": "error", "authenticated": False, "message": str(e)})

    def authenticate_kite():
        """Ensure Kite API is authenticated using token manager"""
        try:
            # Check if trading is enabled via token manager
            if token_manager.is_trading_enabled():
                # Get token from token manager
                access_token = token_manager.get_token()
                
                # Update Kite instance if token has changed
                if kite.access_token != access_token:
                    kite.set_access_token(access_token)
                
                logger.info(f"Kite API authenticated as {token_manager.username}")
                return True
            
            # Token is invalid or expired
            logger.warning("Trading disabled: Token has expired or is invalid")
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

    @app.route('/api/settings')
    def get_settings():
        """Get settings"""
        try:
            # Get token from storage to validate authentication
            token_data = storage.get_token()
            
            if token_data:
                # Get all settings
                settings = storage.get_all_settings()
                
                return jsonify({
                    "status": "success", 
                    "settings": settings,
                    "user": token_data.get('username', 'Unknown')
                })
            
            # No valid token found
            return jsonify({"status": "error", "message": "Authentication required"})
        except Exception as e:
            logger.error(f"Settings retrieval failed: {e}")
            return jsonify({"status": "error", "message": str(e)})

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
            
            # Update settings in storage
            settings_update = {
                'DEFAULT_QUANTITY': str(default_quantity),
                'MAX_TRADE_VALUE': str(max_trade_value),
                'STOP_LOSS_PERCENT': str(stop_loss_percent),
                'TARGET_PERCENT': str(target_percent),
                'MAX_POSITION_SIZE': str(max_position_size)
            }
            storage.update_settings(settings_update)
            
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
            
            # Update settings in storage
            storage.set_setting('TELEGRAM_ENABLED', str(enabled).lower())
            
            # We don't store sensitive data like tokens in the storage,
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
        """Test Telegram notification by sending a test message"""
        try:
            data = request.json
            
            # Create a temporary notifier with the provided credentials
            temp_notifier = TelegramNotifier(
                token=data.get('TELEGRAM_BOT_TOKEN'),
                chat_id=data.get('TELEGRAM_CHAT_ID')
            )
            
            # Send a test message
            result = temp_notifier.send_test_message()
            
            if result:
                return jsonify({"status": "success", "message": "Test notification sent successfully"})
            else:
                return jsonify({"status": "error", "message": "Failed to send test notification"})
        except Exception as e:
            logger.error(f"Error testing Telegram notification: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    def calculate_notional_pnl(trades):
        """
        Calculate notional profit/loss based on position data from Kite API.
        
        Args:
            trades (list): List of trade/position details
        
        Returns:
            dict: Dictionary with P&L information
        """
        if not trades:
            return {
                "total_pnl": 0,
                "total_pnl_percent": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "trades_detail": []
            }
        
        # If trades are from Kite positions API, they already have P&L information
        total_investment = 0
        total_current_value = 0
        winning_trades = 0
        losing_trades = 0
        trades_detail = []
        
        for trade in trades:
            try:
                symbol = trade.get('stock', '')
                action = trade.get('signal', '').upper()
                price = float(trade.get('price', 0))
                quantity = int(trade.get('quantity', 0))
                investment = price * quantity
                
                # If direct PnL is available from Kite API, use it
                if 'pnl' in trade:
                    pnl = float(trade.get('pnl', 0))
                    # For sell positions, the PnL logic is reversed in display
                    if action == 'SELL':
                        pnl = -pnl
                else:
                    # Use calculated P&L from NSE API if no direct PnL
                    current_price = float(trade.get('last_price', price))
                    current_value = current_price * quantity
                    
                    if action == 'BUY':
                        pnl = current_value - investment
                    elif action == 'SELL':
                        pnl = investment - current_value
                    else:
                        pnl = 0
                
                # If we have unrealized and realized P&L from Kite
                unrealized = float(trade.get('unrealized', 0))
                realized = float(trade.get('realised', 0))
                
                # Calculate current value based on investment and P&L
                current_value = investment + pnl
                
                # Calculate P&L percentage
                pnl_percent = (pnl / investment) * 100 if investment > 0 else 0
                
                # Determine if winning or losing trade
                if pnl > 0:
                    winning_trades += 1
                elif pnl < 0:
                    losing_trades += 1
                
                # Update totals
                total_investment += investment
                total_current_value += current_value
                
                # Get current price - either from position data or calculate it
                if 'last_price' in trade:
                    current_price = float(trade.get('last_price', 0))
                else:
                    current_price = price + (pnl / quantity) if quantity > 0 else price
                
                # Add trade details
                trades_detail.append({
                    'symbol': symbol,
                    'action': action,
                    'price': price,
                    'quantity': quantity,
                    'investment': investment,
                    'current_price': current_price,
                    'current_value': current_value,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'unrealized': unrealized,
                    'realized': realized
                })
            except Exception as e:
                logger.error(f"Error calculating P&L for trade {trade}: {e}")
        
        # Calculate total P&L
        total_pnl = total_current_value - total_investment
        total_pnl_percent = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
        
        return {
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "trades_detail": trades_detail
        }

    def get_todays_trades():
        """
        Get all trades that were executed today from Kite positions API instead of local log file.
        
        Returns:
            list: List of trade details for today.
        """
        logger.info("Fetching positions from Kite API...")
        
        if not authenticate_kite():
            logger.error("Kite authentication failed, cannot fetch positions")
            return []
        
        trades = []
        
        try:
            # Fetch positions from Kite API
            positions = kite.get_positions()
            
            if not positions:
                logger.warning("No positions data available from Kite API")
                return []
            
            # Process both day (MIS) and net (CNC) positions
            for position_type in ['day', 'net']:
                if position_type not in positions:
                    continue
                    
                for position in positions[position_type]:
                    # Extract relevant information from position
                    symbol = position.get('tradingsymbol', '')
                    exchange = position.get('exchange', '')
                    
                    # Format symbol with exchange prefix if not already there
                    if not symbol.startswith("NSE:") and not symbol.startswith("NFO:"):
                        if exchange:
                            symbol = f"{exchange}:{symbol}"
                    
                    # Determine if this is a buy or sell position based on quantity
                    quantity = position.get('quantity', 0)
                    action = "BUY" if quantity > 0 else "SELL"
                    
                    # If quantity is negative (short position), make it positive for display
                    quantity = abs(quantity)
                    
                    # Get price details
                    price = position.get('average_price', 0)
                    last_price = position.get('last_price', 0)
                    
                    # Calculate trade value
                    value = price * quantity
                    
                    # Create trade object
                    trade = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "stock": symbol,
                        "signal": action,
                        "price": price,
                        "quantity": quantity,
                        "value": value,
                        "scanner": "Kite Positions",  # Default scanner name
                        "order_id": "",               # Not available from positions API
                        "pnl": position.get('pnl', 0),
                        "unrealized": position.get('unrealised', 0),
                        "realized": position.get('realised', 0),
                        "product": "MIS" if position_type == 'day' else "CNC",  # Add product type
                        "last_price": last_price
                    }
                    
                    trades.append(trade)
            
            logger.info(f"Found {len(trades)} positions from Kite API")
            return trades
        except Exception as e:
            logger.error(f"Error fetching positions from Kite API: {e}")
            return []

    def send_day_summary():
        """Send a summary of today's trading activity via Telegram"""
        logger.info("Sending daily trading summary...")
        
        trades = get_todays_trades()
        pnl_data = calculate_notional_pnl(trades)
        
        telegram.notify_day_summary(trades, pnl_data)
        
        logger.info(f"Daily summary sent with {len(trades)} trades and P&L: ₹{pnl_data['total_pnl']:.2f}")

    @app.route('/api/trades/pnl', methods=['GET'])
    def get_trades_pnl():
        """Get notional P&L for today's trades"""
        try:
            trades = get_todays_trades()
            pnl_data = calculate_notional_pnl(trades)
            
            return jsonify({
                "status": "success", 
                "data": {
                    "trades_count": len(trades),
                    "total_pnl": round(pnl_data["total_pnl"], 2),
                    "total_pnl_percent": round(pnl_data["total_pnl_percent"], 2),
                    "winning_trades": pnl_data["winning_trades"],
                    "losing_trades": pnl_data["losing_trades"],
                    "trades_detail": pnl_data["trades_detail"]
                }
            })
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/telegram/day-summary', methods=['GET'])
    def trigger_day_summary():
        """Manually trigger a day summary notification"""
        try:
            trades = get_todays_trades()
            pnl_data = calculate_notional_pnl(trades)
            result = telegram.notify_day_summary(trades, pnl_data)
            
            if result:
                return jsonify({
                    "status": "success", 
                    "message": f"Day summary sent successfully with {len(trades)} trades"
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": "Failed to send day summary notification"
                })
        except Exception as e:
            logger.error(f"Error sending day summary: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # Add shutdown hook to clean up resources
    @app.teardown_appcontext
    def shutdown_memory_optimizer(exception=None):
        memory_optimizer.stop_optimization()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    # Log the current time in IST
    now = datetime.now(IST)
    logger.info(f"Starting application at {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # For the full app only, start the required services
    # Check if we're running the market closed app or the full app
    if not BYPASS_MARKET_HOURS and not is_market_open():
        # Market is closed - just run the lightweight version without other services
        logger.info("Running lightweight market-closed version with memory optimization")
        app.run(host="0.0.0.0", port=port, debug=debug)
    else:
        # Market is open - run the full app with all services
        # Attempt to authenticate to check if token is valid
        authenticate_kite()
        
        # Start the auth checker scheduler
        start_scheduler()
        
        # Schedule the daily summary task - default at 3:30 PM IST (market close time)
        scheduler.add_job(send_day_summary, 'cron', hour=15, minute=30, timezone='Asia/Kolkata')
        scheduler.start()
    
        # Start the server (full app)
        logger.info(f"Starting webhook server on port {port} with memory optimization")
        app.run(host="0.0.0.0", port=port, debug=debug) 