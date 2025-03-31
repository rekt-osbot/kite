#!/usr/bin/env python
"""
Kite Rate Limiter Module

This module provides a wrapper around the KiteConnect API client that implements
rate limiting to prevent API call rate limit errors. It uses a token bucket algorithm
to control the rate of requests sent to the Zerodha Kite API.
"""
import logging
import time
import threading
from functools import wraps
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TokenBucket:
    """
    Implements the token bucket algorithm for rate limiting.
    
    Tokens are added to the bucket at a fixed rate. Each API call consumes
    one or more tokens. If there are not enough tokens, the call is blocked
    until enough tokens are available.
    """
    def __init__(self, rate=3.0, capacity=10.0):
        """
        Initialize a token bucket with specified rate and capacity.
        
        Args:
            rate (float): Token refill rate (tokens per second)
            capacity (float): Maximum number of tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.RLock()
    
    def consume(self, count=1.0):
        """
        Consume tokens from the bucket.
        
        Args:
            count (float): Number of tokens to consume
            
        Returns:
            float: Wait time in seconds before tokens are available
        """
        with self.lock:
            # Refill the bucket
            now = time.time()
            time_passed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + time_passed * self.rate)
            self.last_refill = now
            
            # Check if we have enough tokens
            if count <= self.tokens:
                # We have enough tokens, consume them
                self.tokens -= count
                return 0.0
            else:
                # Not enough tokens, calculate wait time
                wait_time = (count - self.tokens) / self.rate
                return wait_time

class RateLimitedKiteConnect:
    """
    A wrapper around KiteConnect that implements rate limiting.
    
    This class proxies calls to the underlying KiteConnect instance but
    applies rate limiting to ensure that we don't exceed the API rate limits.
    """
    # Define cost for different API operations (default is 1 token per call)
    # Higher-cost operations (like order placement) consume more tokens
    OPERATION_COSTS = {
        'default': 1.0,        # Default cost for most operations
        'place_order': 2.0,    # Order placement is higher cost
        'modify_order': 2.0,   # Order modification is higher cost
        'cancel_order': 2.0,   # Order cancellation is higher cost
        'orders': 2.0,         # Getting order history is higher cost
        'trades': 2.0,         # Getting trade history is higher cost
    }
    
    def __init__(self, kite_instance, rate=3.0, capacity=10.0):
        """
        Initialize the rate limiter with a KiteConnect instance.
        
        Args:
            kite_instance: An instance of KiteConnect
            rate (float): Maximum number of API calls per second
            capacity (float): Maximum burst capacity
        """
        self.kite = kite_instance
        self.bucket = TokenBucket(rate, capacity)
        logger.info(f"Created rate-limited KiteConnect with rate={rate} calls/sec, capacity={capacity}")
    
    def __getattr__(self, name):
        """
        Proxy attribute access to the underlying KiteConnect instance.
        
        If the attribute is a callable (method), wrap it with rate limiting logic.
        Otherwise, return the attribute directly from the underlying instance.
        """
        attr = getattr(self.kite, name)
        
        if not callable(attr):
            # For non-callable attributes, return them directly
            return attr
        
        @wraps(attr)
        def rate_limited_method(*args, **kwargs):
            # Determine the cost of this operation
            cost = self.OPERATION_COSTS.get(name, self.OPERATION_COSTS['default'])
            
            # Try to consume tokens (this will wait if necessary)
            wait_time = self.bucket.consume(cost)
            if wait_time > 0:
                logger.debug(f"Rate limiting: Waiting {wait_time:.2f}s for {name} (cost: {cost})")
                time.sleep(wait_time)
            
            # Call the underlying method
            start_time = time.time()
            try:
                result = attr(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"API call to {name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                if "rate limit" in str(e).lower():
                    logger.warning(f"Rate limit error occurred despite rate limiting: {e}")
                    # Implement backoff if necessary
                    time.sleep(1.0)  # Add additional delay for rate limit errors
                raise  # Re-raise the exception after logging
        
        return rate_limited_method

def get_rate_limited_kite(kite_instance, rate=3.0, capacity=10.0):
    """
    Utility function to create a rate-limited KiteConnect wrapper.
    
    Args:
        kite_instance: An instance of KiteConnect
        rate (float): Maximum number of API calls per second
        capacity (float): Maximum burst capacity
        
    Returns:
        RateLimitedKiteConnect: A rate-limited wrapper around the original instance
    """
    return RateLimitedKiteConnect(kite_instance, rate, capacity)

# Example usage
if __name__ == "__main__":
    logger.info("Kite Rate Limiter example")
    
    try:
        # Try to import kiteconnect if available
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key="your_api_key")
        
        # Create a rate-limited version
        limited_kite = get_rate_limited_kite(kite)
        
        # Now use limited_kite just like a regular KiteConnect object
        # Example (would need actual authentication):
        # limited_kite.margins()
        # limited_kite.positions()
        
        logger.info("Rate limiter ready. Use the get_rate_limited_kite() function to create a rate-limited KiteConnect.")
        
    except ImportError:
        logger.info("KiteConnect library not found. This is just a demonstration.")
        
        # Create a mock KiteConnect for demonstration
        class MockKiteConnect:
            def __init__(self, api_key=None):
                self.api_key = api_key
            
            def margins(self):
                logger.info("Mock: Getting margins")
                time.sleep(0.1)  # Simulate API call
                return {"margins": "data"}
            
            def positions(self):
                logger.info("Mock: Getting positions")
                time.sleep(0.1)  # Simulate API call
                return {"positions": "data"}
            
            def place_order(self, **kwargs):
                logger.info("Mock: Placing order")
                time.sleep(0.1)  # Simulate API call
                return {"order_id": "123456"}
        
        # Create an instance of the mock KiteConnect
        mock_kite = MockKiteConnect(api_key="demo_key")
        
        # Create a rate-limited version
        limited_kite = get_rate_limited_kite(mock_kite)
        
        # Example usage
        logger.info("\nTesting rate limiter with mock KiteConnect...")
        for i in range(5):
            logger.info(f"Call {i+1}: Margins")
            limited_kite.margins()
        
        for i in range(3):
            logger.info(f"Call {i+1}: Place Order (higher cost)")
            limited_kite.place_order(tradingsymbol="INFY", exchange="NSE", 
                                  transaction_type="BUY", quantity=1, 
                                  order_type="MARKET", product="CNC")
        
        logger.info("Rate limiting test complete")
    
    logger.info("Kite Rate Limiter module example completed.") 