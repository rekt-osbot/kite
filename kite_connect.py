import os
import hashlib
import requests
import json
from datetime import datetime
from urllib.parse import urlencode
import webbrowser
from dotenv import load_dotenv
import logging
from token_manager import token_manager

# Configure logging
logger = logging.getLogger(__name__)

class KiteConnect:
    """
    A class to connect with Zerodha Kite API, handle authentication,
    and perform trading operations.
    """
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # API credentials
        self.api_key = os.getenv("KITE_API_KEY")
        self.api_secret = os.getenv("KITE_API_SECRET")
        
        # Base URLs
        self.login_url = "https://kite.zerodha.com/connect/login"
        self.api_url = "https://api.kite.trade"
        
        # Headers
        self.headers = {
            "X-Kite-Version": "3"
        }
        
        # Get access token from token manager
        self.access_token = token_manager.get_token()
        if self.access_token:
            self.set_access_token(self.access_token)
    
    def set_access_token(self, access_token):
        """Set the access token for API requests"""
        self.access_token = access_token
        self.headers["Authorization"] = f"token {self.api_key}:{self.access_token}"
    
    def get_login_url(self):
        """Get the Zerodha login URL for web authentication flow"""
        redirect_url = os.getenv("REDIRECT_URL", "")
        login_params = {
            "v": 3,
            "api_key": self.api_key,
            "redirect_url": redirect_url
        }
        
        return f"{self.login_url}?{urlencode(login_params)}"
    
    def login(self):
        """
        Start the login flow by opening the Kite login page in a browser.
        The user will be redirected to a URL with a request token after login.
        """
        login_params = {
            "v": 3,
            "api_key": self.api_key
        }
        
        login_url = f"{self.login_url}?{urlencode(login_params)}"
        print(f"Opening login URL in browser: {login_url}")
        print("Please login and then paste the redirect URL here:")
        
        webbrowser.open(login_url)
        redirect_url = input("Enter the redirect URL after login: ").strip()
        
        # Extract request token from the redirect URL
        # The URL will be like: your_redirect_uri?request_token=xxx&action=login&status=success
        import urllib.parse
        parsed = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        request_token = query_params.get('request_token', [''])[0]
        
        if not request_token:
            raise Exception("Could not extract request token from the redirect URL")
        
        print(f"Extracted request token: {request_token}")
        return self.generate_session(request_token)
    
    def generate_session(self, request_token):
        """
        Exchange the request token for an access token
        """
        # Create checksum
        checksum_data = f"{self.api_key}{request_token}{self.api_secret}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        
        # Request body
        data = {
            "api_key": self.api_key,
            "request_token": request_token,
            "checksum": checksum
        }
        
        # Make the API call
        response = requests.post(
            f"{self.api_url}/session/token",
            headers=self.headers,
            data=data
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to generate session: {response.text}")
        
        data = response.json()["data"]
        access_token = data["access_token"]
        
        # Set the access token using token manager
        self.set_access_token(access_token)
        
        # Save token to token manager with user details
        try:
            profile_data = self.get_profile()
            user_id = profile_data.get('user_id')
            username = profile_data.get('user_name')
            token_manager.save_token(user_id, username, access_token)
            logger.info(f"Successfully authenticated as {username}")
        except Exception as e:
            logger.error(f"Failed to get user profile after authentication: {e}")
            # Fall back to saving token without user details
            token_manager.save_token("unknown", "Zerodha User", access_token)
        
        return data
    
    def get_profile(self):
        """Get user profile information"""
        response = requests.get(
            f"{self.api_url}/user/profile",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get profile: {response.text}")
        
        return response.json()["data"]
    
    def get_margins(self, segment=None):
        """Get user margins"""
        endpoint = f"{self.api_url}/user/margins"
        if segment:
            endpoint = f"{endpoint}/{segment}"
        
        response = requests.get(
            endpoint,
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get margins: {response.text}")
        
        return response.json()["data"]
    
    def get_orders(self):
        """Get user's order history"""
        response = requests.get(
            f"{self.api_url}/orders",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get orders: {response.text}")
        
        return response.json()["data"]
    
    def get_positions(self):
        """Get user's current positions"""
        response = requests.get(
            f"{self.api_url}/portfolio/positions",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get positions: {response.text}")
        
        return response.json()["data"]
    
    def get_quote(self, instruments):
        """
        Get market quotes and depth for one or more instruments.
        
        Parameters:
        instruments (str or list): Instrument keys (exchange:tradingsymbol) as a comma-separated string or a list
        
        Returns:
        dict: Market quotes and market depth
        """
        if isinstance(instruments, list):
            instruments = ",".join(instruments)
            
        response = requests.get(
            f"{self.api_url}/quote",
            params={"i": instruments},
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get quotes: {response.text}")
        
        return response.json()["data"]
    
    def place_order(self, variety, params):
        """
        Place an order on Zerodha Kite
        
        Parameters:
        variety (str): Order variety (regular, amo, co, iceberg, auction)
        params (dict): Order parameters
            - exchange (str): NSE, BSE, NFO, etc.
            - tradingsymbol (str): Trading symbol
            - transaction_type (str): BUY or SELL
            - quantity (int): Order quantity
            - product (str): MIS, CNC, NRML, etc.
            - order_type (str): MARKET, LIMIT, SL, SL-M
            - price (float, optional): Required for LIMIT orders
            - trigger_price (float, optional): Required for SL and SL-M orders
            - disclosed_quantity (int, optional): Disclosed quantity
            - validity (str, optional): DAY or IOC
            - tag (str, optional): Tag for the order
        
        Returns:
        str: Order ID
        """
        # Verify trading is enabled before placing orders
        if not token_manager.is_trading_enabled():
            raise Exception("Trading is currently disabled - Token is expired or invalid")
            
        response = requests.post(
            f"{self.api_url}/orders/{variety}",
            headers=self.headers,
            data=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to place order: {response.text}")
        
        return response.json()["data"]["order_id"]
    
    def order_history(self, order_id):
        """
        Get history of an order
        
        Parameters:
        order_id (str): Order ID
        
        Returns:
        list: Order history
        """
        response = requests.get(
            f"{self.api_url}/orders/{order_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get order history: {response.text}")
        
        return response.json()["data"]
    
    def cancel_order(self, variety, order_id):
        """
        Cancel an order
        
        Parameters:
        variety (str): Order variety (regular, amo, co)
        order_id (str): Order ID
        
        Returns:
        str: Order ID
        """
        # Verify trading is enabled before cancelling orders
        if not token_manager.is_trading_enabled():
            raise Exception("Trading is currently disabled - Token is expired or invalid")
            
        response = requests.delete(
            f"{self.api_url}/orders/{variety}/{order_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to cancel order: {response.text}")
        
        return response.json()["data"]["order_id"]
    
    def logout(self):
        """Logout and invalidate the access token"""
        response = requests.delete(
            f"{self.api_url}/session/token",
            params={"api_key": self.api_key, "access_token": self.access_token},
            headers=self.headers
        )
        
        # Clear token in token manager regardless of API response
        try:
            if response.status_code == 200:
                logger.info("Successfully logged out from Zerodha API")
            storage = token_manager.storage  # Access file storage
            storage.clear()  # Clear stored data
            logger.info("Cleared stored token data")
        except Exception as e:
            logger.error(f"Error clearing token data: {e}")
        
        # Clear instance variables
        self.access_token = None
        self.headers.pop("Authorization", None)
        
        return True

def main():
    kite = KiteConnect()
    
    # Check if access token exists and is valid
    try:
        if token_manager.is_trading_enabled():
            profile = kite.get_profile()
            print(f"Already logged in as {profile['user_name']}")
        else:
            print("Token expired or invalid. Login required.")
            kite.login()
    except Exception as e:
        print(f"Error: {e}")
        print("Need to login again...")
        kite.login()
    
    # Get and display user information
    profile = kite.get_profile()
    print(f"\nProfile Information:")
    print(f"User ID: {profile['user_id']}")
    print(f"User Name: {profile['user_name']}")
    print(f"Email: {profile['email']}")
    print(f"Broker: {profile['broker']}")
    
    # Get and display margin information
    margins = kite.get_margins()
    print(f"\nMargin Information:")
    for segment, data in margins.items():
        print(f"\n{segment.upper()} Segment:")
        print(f"Net: {data['net']}")
        print(f"Available Cash: {data['available']['cash']}")
        
    # Get and display positions
    try:
        positions = kite.get_positions()
        print("\nPositions:")
        if positions:
            for pos_type, positions_list in positions.items():
                if positions_list:
                    print(f"\n{pos_type.upper()}:")
                    for position in positions_list:
                        print(f"Symbol: {position['tradingsymbol']}, Quantity: {position['quantity']}, Avg Price: {position['average_price']}")
                else:
                    print(f"No {pos_type} positions")
        else:
            print("No positions found")
    except Exception as e:
        print(f"Error fetching positions: {e}")
    
    # Get and display order history
    try:
        orders = kite.get_orders()
        print("\nOrder History:")
        if orders:
            for order in orders:
                print(f"Order ID: {order['order_id']}, Symbol: {order['tradingsymbol']}, Status: {order['status']}")
        else:
            print("No orders found")
    except Exception as e:
        print(f"Error fetching orders: {e}")

if __name__ == "__main__":
    main() 