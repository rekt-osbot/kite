# Kite Trading Bot - Developer Documentation

## Project Overview

This project is an algorithmic trading bot that integrates Zerodha's Kite API with ChartInk webhook alerts to automate stock trading on India's National Stock Exchange (NSE). The system features rate-limited API interactions, market status determination with holiday awareness, and a modular architecture designed to prevent circular dependencies.

## Core Architecture

### Key Modules

| Module | Purpose |
|--------|---------|
| `chartink_webhook.py` | Flask application that processes webhook requests and executes trades |
| `railway_start.py` | Application entry point that handles market hours logic |
| `kite_connect.py` | Zerodha Kite API integration wrapper |
| `kite_rate_limiter.py` | Token bucket rate limiter for API calls |
| `nse_holidays.py` | NSE market holiday and operation status determination |
| `dependency_resolver.py` | Lazy loading mechanism to prevent circular dependencies |
| `file_storage.py` | File-based JSON storage for tokens and settings |
| `telegram_notifier.py` | Notification system for system status and trade alerts |
| `scheduler.py` | Background task scheduler |

### Design Patterns

- **Token Bucket Pattern**: Used for API rate limiting 
- **Lazy Loading**: Used to resolve circular import dependencies
- **Webhook Processing**: Event-driven architecture for trade signals
- **Stateless Operation**: Designed to minimize persistent state requirements

## Technical Implementations

### 1. API Rate Limiting

The system implements a token bucket algorithm in `kite_rate_limiter.py` to prevent exceeding Zerodha's API rate limits of 3 requests/second. Implementation features:

- Configurable request rate and bucket capacity
- Operation cost weighting (order operations cost more than data retrieval)
- Automatic request throttling with backoff

Example usage:
```python
from kite_rate_limiter import get_rate_limited_kite
from kite_connect import KiteConnect

# Create a rate-limited Kite instance
kite_base = KiteConnect(api_key="API_KEY")
kite = get_rate_limited_kite(kite_base)

# Use normally - all API calls are now rate-limited
profile = kite.profile()
```

### 2. Market Status Determination

The `nse_holidays.py` module provides market status intelligence:

- Holiday calendar for the NSE (hardcoded for 2025)
- Market hour validation (9:15 AM - 3:30 PM IST, Monday-Friday)
- Next trading day calculation that skips holidays
- Detailed market status reporting

```python
from nse_holidays import is_market_holiday, get_market_status

# Get current market status
status = get_market_status()
if status['is_open']:
    # Execute trading logic
else:
    # Handle closed market scenario
    logger.info(f"Market closed: {status['message']}")
    next_open = status['next_market_open']
```

### 3. Circular Dependency Resolution

The `dependency_resolver.py` implements lazy module imports to break circular dependencies:

```python
from dependency_resolver import lazy_import

# Lazy load instead of direct import 
ModuleB = lazy_import('module_b', 'ModuleB')

# Later when needed:
instance = ModuleB()  # Only loaded at this point
```

### 4. Signal Processing Logic

The webhook handler parses ChartInk alerts and determines trading intent through keyword analysis:

```json
{
    "stocks": "STOCK1,STOCK2,STOCK3",
    "trigger_prices": "100.5,200.5,300.5",
    "triggered_at": "2:34 pm",
    "scan_name": "Short term breakouts",
    "scan_url": "short-term-breakouts",
    "alert_name": "Alert for Short term breakouts"
}
```

Buy/sell signal classification uses these keyword sets:
- **Buy Keywords**: "buy", "bull", "bullish", "long", "breakout", "up", "uptrend", "support", "bounce", "reversal", "upside"
- **Sell Keywords**: "sell", "bear", "bearish", "short", "breakdown", "down", "downtrend", "resistance", "fall", "decline"

### 5. File-Based Storage

The `file_storage.py` provides a lightweight alternative to database storage:

- JSON file-based persistence
- Token management with expiration handling
- Settings storage with defaults
- Thread-safe operations

## System Constants and Configurations

### Environmental Variables

Key configuration parameters are loaded from environment variables:

```
KITE_API_KEY          # Zerodha API key
KITE_API_SECRET       # Zerodha API secret
DEFAULT_QUANTITY      # Default order quantity
MAX_TRADE_VALUE       # Maximum value per trade
STOP_LOSS_PERCENT     # Default stop-loss percentage
TARGET_PERCENT        # Default target percentage
MAX_POSITION_SIZE     # Maximum position size
API_RATE_LIMIT        # API calls per second (default: 3)
PORT                  # Server port (default: 5000)
BYPASS_MARKET_HOURS   # Testing flag to bypass market hours check
```

### Market Constants

Market operation parameters:
- Trading hours: 9:15 AM - 3:30 PM IST
- Pre-market session: 9:00 AM - 9:15 AM IST
- Weekly closed days: Saturday and Sunday
- Special holiday closures defined in `NSE_HOLIDAYS_2025` dictionary

## Trading Logic Flow

1. Webhook receives signal from ChartInk
2. Signal passes preliminary validation
3. Stock symbols and trigger prices are extracted
4. Trading intent (buy/sell) is determined from scan name or explicit action field
5. Available margin is checked for trade viability
6. Position size is calculated based on available funds and configured limits
7. Market order is placed with delivery (CNC) order type
8. Stop-loss order is placed at configured percentage from entry
9. Trade details are logged and notifications sent
10. Dashboard is updated with new positions and orders

## Technical Limitations

- The Zerodha API token expires daily at 6 AM IST and requires re-authentication
- API rate limits of 3 requests/second must be respected
- Order modifications have higher API rate costs than data retrieval
- Market status checking relies on the accuracy of the hardcoded holiday calendar

## Recent Improvements

1. ✅ **Market Status Determination**: Implemented the `nse_holidays.py` module for accurate market status checking
2. ✅ **API Rate Limiting**: Added the token bucket rate limiter to prevent API rate limit violations
3. ✅ **Circular Dependency Resolution**: Implemented lazy imports to avoid circular import errors

## For AI Developers

When making modifications to this codebase, consider:

1. **Rate Limiting**: All API interactions should go through the rate-limited client
2. **Market Hours**: Trading logic should check market status before executing trades
3. **Error Handling**: API errors should be caught and handled appropriately 
4. **Logging**: Maintain detailed logging for troubleshooting
5. **Dependencies**: Use lazy imports for any cross-module dependencies that could become circular 