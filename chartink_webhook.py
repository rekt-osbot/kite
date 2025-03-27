import json
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, redirect, send_from_directory
from dotenv import load_dotenv
from kite_connect import KiteConnect
from scheduler import start_scheduler

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

# Trading configuration
DEFAULT_QUANTITY = int(os.getenv("DEFAULT_QUANTITY", 1))
MAX_TRADE_VALUE = float(os.getenv("MAX_TRADE_VALUE", 5000))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", 2))
TARGET_PERCENT = float(os.getenv("TARGET_PERCENT", 4))

# Authentication routes
@app.route('/')
def index():
    """Home page"""
    return redirect('/auth/refresh')

@app.route('/auth/refresh')
def auth_refresh():
    """Show the token refresh page"""
    return send_from_directory('auth', 'refresh.html')

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    
    # Attempt to authenticate to check if token is valid
    authenticate_kite()
    
    # Start the auth checker scheduler
    start_scheduler()
    
    logger.info(f"Starting webhook server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug) 