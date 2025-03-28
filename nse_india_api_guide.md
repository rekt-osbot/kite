# NSE India API Guide

## Introduction

This guide explains how to use the NSE India API library (unofficial) to fetch real-time stock quotes and other market data. The library provides a simple Python interface to interact with NSE (National Stock Exchange of India) data, which can be integrated with trading bots or other financial applications.

## Installation

Install the library using pip:

```bash
pip install -U nse
```

## Basic Usage

### Initializing the API

```python
from nse import NSE

# Create a download folder for storing cache and downloaded files
import os
from pathlib import Path

if not os.path.exists('downloads'):
    os.mkdir('downloads')

# Initialize NSE API
nse = NSE(download_folder='./downloads')

# When done, close the session
nse.exit()
```

Alternatively, use the context manager to auto-close the session:

```python
with NSE(download_folder='./downloads') as nse:
    # Use the NSE API methods here
    # Session will be automatically closed when the block exits
    pass
```

## Fetching Stock Quotes

### Basic Quote Data

To fetch basic quote data for a stock:

```python
with NSE(download_folder='./downloads') as nse:
    # Get quote for a single stock
    quote = nse.quote('RELIANCE')
    
    # Extract price information
    if 'priceInfo' in quote:
        price_info = quote['priceInfo']
        last_price = price_info.get('lastPrice')
        change = price_info.get('change')
        pct_change = price_info.get('pChange')
        print(f"RELIANCE: ₹{last_price} ({pct_change}%)")
```

### Quote Response Structure

The `quote()` method returns a dictionary with the following structure:

```python
{
    "info": {
        "symbol": "RELIANCE",
        "companyName": "Reliance Industries Limited",
        "industry": "Refineries & Marketing",
        # Other company info...
    },
    "priceInfo": {
        "lastPrice": 1275.1,
        "change": -3.1,
        "pChange": -0.24,
        "previousClose": 1278.2,
        "open": 1280.0,
        "intraDayHighLow": {
            "min": 1269.0,
            "max": 1295.75
        },
        # Other price data...
    },
    # Other sections...
}
```

### Extracting Key Data

Here's how to extract the most important data for trading:

```python
def extract_trading_data(quote_data):
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
```

## Fetching Multiple Stock Quotes

To fetch quotes for multiple stocks:

```python
def get_quotes(symbols):
    quotes = []
    
    with NSE(download_folder='./downloads') as nse:
        for symbol in symbols:
            try:
                # Get quote data
                quote_data = nse.quote(symbol)
                
                # Extract trading data
                trading_data = extract_trading_data(quote_data)
                quotes.append(trading_data)
                
                # Respect rate limiting (3 requests per second)
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error fetching quote for {symbol}: {e}")
    
    return quotes
```

## Integration with Trading Bots

When integrating with a trading bot, you'll want to:

1. Fetch real-time quotes
2. Make trading decisions based on the data
3. Execute trades through your broker's API

### Example: Simple Integration

```python
import time
from nse import NSE
from your_broker_api import BrokerAPI  # Replace with your broker's API

class TradingBot:
    def __init__(self):
        self.nse = NSE(download_folder='./downloads')
        self.broker = BrokerAPI(api_key='YOUR_API_KEY', api_secret='YOUR_API_SECRET')
        self.watchlist = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
    
    def fetch_market_data(self):
        quotes = []
        for symbol in self.watchlist:
            quote_data = self.nse.quote(symbol)
            trading_data = extract_trading_data(quote_data)
            quotes.append(trading_data)
            time.sleep(0.5)  # Respect rate limiting
        return quotes
    
    def analyze_data(self, quotes):
        buy_signals = []
        sell_signals = []
        
        for quote in quotes:
            # Your trading strategy here
            # Example: Simple moving average crossover
            if self.is_buy_signal(quote):
                buy_signals.append(quote['symbol'])
            elif self.is_sell_signal(quote):
                sell_signals.append(quote['symbol'])
        
        return buy_signals, sell_signals
    
    def execute_trades(self, buy_signals, sell_signals):
        for symbol in buy_signals:
            quantity = self.calculate_position_size(symbol)
            self.broker.place_order(
                symbol=symbol,
                quantity=quantity,
                order_type='MARKET',
                transaction_type='BUY'
            )
            print(f"BUY order placed for {symbol}, quantity: {quantity}")
            
        for symbol in sell_signals:
            holdings = self.broker.get_holdings()
            for holding in holdings:
                if holding['symbol'] == symbol:
                    self.broker.place_order(
                        symbol=symbol,
                        quantity=holding['quantity'],
                        order_type='MARKET',
                        transaction_type='SELL'
                    )
                    print(f"SELL order placed for {symbol}, quantity: {holding['quantity']}")
    
    def run(self):
        try:
            print("Starting trading bot...")
            while True:
                quotes = self.fetch_market_data()
                buy_signals, sell_signals = self.analyze_data(quotes)
                self.execute_trades(buy_signals, sell_signals)
                
                # Wait before next cycle
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            print("Bot stopped by user")
        finally:
            # Clean up
            self.nse.exit()
            print("Session closed")

# Run the bot
if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
```

## Best Practices

### Rate Limiting

NSE limits the API to 3 requests per second. To avoid being blocked:

1. Add delays between requests (0.5-1 second is recommended)
2. Batch your requests and cache responses where possible
3. Don't make unnecessary requests

```python
def get_quotes_with_rate_limiting(symbols):
    with NSE(download_folder='./downloads') as nse:
        quotes = []
        for symbol in symbols:
            quote_data = nse.quote(symbol)
            quotes.append(quote_data)
            time.sleep(0.5)  # 500ms delay between requests
    return quotes
```

### Error Handling

Always implement proper error handling:

```python
try:
    quote_data = nse.quote(symbol)
    # Process data
except Exception as e:
    print(f"Error fetching quote for {symbol}: {e}")
    # Implement fallback strategy
    # e.g., use cached data or skip this symbol
```

### Session Management

Always close the NSE session when done:

```python
# Using context manager (recommended)
with NSE(download_folder='./downloads') as nse:
    # Your code here
    pass  # Session automatically closed

# Manual close
nse = NSE(download_folder='./downloads')
try:
    # Your code here
finally:
    nse.exit()  # Explicitly close the session
```

## Advanced Features

### Fetching Historical Data

For technical analysis or backtesting, you might need historical data:

```python
from datetime import datetime, timedelta

# Get equity bhavcopy (daily price and volume data)
yesterday = datetime.now() - timedelta(days=1)
bhavcopy_file = nse.equityBhavcopy(date=yesterday)
```

### Corporate Actions

To track dividends, splits, and other corporate actions:

```python
# Get corporate actions
actions = nse.actions()
for action in actions[:5]:  # Show first 5 actions
    print(f"{action['symbol']}: {action['subject']} on {action['exDate']}")
```

### Market Status

Check if the market is open:

```python
status = nse.status()
for market in status:
    print(f"{market['market']}: {market['marketStatus']}")
```

## Conclusion

The NSE India API library provides a powerful way to access market data for automated trading systems. By following this guide, you can integrate real-time stock quotes into your trading bot to make data-driven investment decisions.

Remember to implement proper error handling, respect rate limits, and always close the NSE session when done to avoid resource leaks. 