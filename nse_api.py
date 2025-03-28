import os
import time
import logging
from pathlib import Path
from nse import NSE

logger = logging.getLogger(__name__)

class NSEIndiaAPI:
    """
    A wrapper for the NSE India API to fetch stock quotes and other market data.
    """
    
    def __init__(self):
        # Create a download folder for storing cache and downloaded files
        if not os.path.exists('downloads'):
            os.makedirs('downloads', exist_ok=True)
        
        self.nse = None
    
    def initialize(self):
        """Initialize the NSE API client if not already initialized"""
        if self.nse is None:
            try:
                self.nse = NSE(download_folder='./downloads')
                logger.info("NSE API client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing NSE API client: {e}")
                return False
        return True
    
    def close(self):
        """Close the NSE API client session"""
        if self.nse:
            try:
                self.nse.exit()
                self.nse = None
                logger.info("NSE API client session closed")
            except Exception as e:
                logger.error(f"Error closing NSE API session: {e}")
    
    def get_quote(self, symbol):
        """
        Get the current quote for a stock symbol.
        
        Args:
            symbol (str): The stock symbol to fetch (e.g., "RELIANCE")
        
        Returns:
            dict: A dictionary with extracted trading data or None if error
        """
        if not self.initialize():
            return None
        
        try:
            # Remove exchange prefix if present
            clean_symbol = symbol
            if "NSE:" in clean_symbol:
                clean_symbol = clean_symbol.replace("NSE:", "")
            elif "NFO:" in clean_symbol:
                clean_symbol = clean_symbol.replace("NFO:", "")
            
            # Get quote data from NSE
            quote_data = self.nse.quote(clean_symbol)
            
            # Extract trading data
            trading_data = self._extract_trading_data(quote_data)
            logger.debug(f"Successfully fetched quote for {symbol}: {trading_data}")
            return trading_data
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
        
    def get_quotes(self, symbols):
        """
        Get quotes for multiple stock symbols with rate limiting.
        
        Args:
            symbols (list): List of stock symbols to fetch
        
        Returns:
            dict: A dictionary mapping symbols to their trading data
        """
        if not self.initialize():
            return {}
        
        quotes = {}
        
        for symbol in symbols:
            try:
                quotes[symbol] = self.get_quote(symbol)
                # Respect rate limiting (max 3 requests per second)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error fetching quote for {symbol}: {e}")
                quotes[symbol] = None
        
        return quotes
        
    def _extract_trading_data(self, quote_data):
        """
        Extract relevant trading data from the quote response.
        
        Args:
            quote_data (dict): The raw quote data from NSE API
        
        Returns:
            dict: A dictionary with extracted trading data
        """
        trading_data = {}
        
        # Basic company info
        if 'info' in quote_data:
            info = quote_data['info']
            trading_data['symbol'] = info.get('symbol')
            trading_data['company_name'] = info.get('companyName')
            trading_data['industry'] = info.get('industry')
        
        # Price information
        if 'priceInfo' in quote_data:
            price_info = quote_data['priceInfo']
            trading_data['last_price'] = price_info.get('lastPrice')
            trading_data['change'] = price_info.get('change')
            trading_data['pct_change'] = price_info.get('pChange')
            trading_data['prev_close'] = price_info.get('previousClose')
            trading_data['open'] = price_info.get('open')
            
            # High/Low
            if 'intraDayHighLow' in price_info:
                hl = price_info['intraDayHighLow']
                trading_data['high'] = hl.get('max')
                trading_data['low'] = hl.get('min')
        
        return trading_data

# Singleton instance
nse_api = NSEIndiaAPI()

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the API
    api = NSEIndiaAPI()
    try:
        print("Testing NSE API...")
        quote = api.get_quote("RELIANCE")
        print(f"RELIANCE quote: {quote}")
    finally:
        api.close() 