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
| `token_manager.py` | Centralized token management with expiration handling |
| `token_status.py` | Token status UI endpoints and monitoring dashboard |
| `memory_optimizer.py` | Memory usage optimization for Railway deployment |

### Design Patterns

- **Token Bucket Pattern**: Used for API rate limiting 
- **Lazy Loading**: Used to resolve circular import dependencies
- **Webhook Processing**: Event-driven architecture for trade signals
- **Stateless Operation**: Designed to minimize persistent state requirements
- **Resource Optimization**: Adaptive resource usage based on market status

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

### 4. Token Management and Expiration Handling

The `token_manager.py` module provides centralized token management:

- Reliable detection of token expiration at 6 AM IST
- Clear user notifications for token renewal with detailed instructions
- Graceful degradation by disabling trading when tokens expire
- Centralized token storage and validation

Example usage:
```python
from token_manager import token_manager

# Check token validity before trading
if token_manager.is_token_valid():
    # Execute trading logic
else:
    # Handle expired token with user notification
    token_manager.notify_token_expired()
```

### 5. Memory Optimization for Railway Deployment

The `memory_optimizer.py` module implements resource optimization strategies:

- Adaptive garbage collection based on application state
- Module unloading to free memory in long-running processes
- Dictionary optimization to remove empty values
- Background cleanup thread with minimal overhead

Example usage:
```python
import memory_optimizer

# Start optimization in the background
memory_optimizer.start_optimization()

# Clean up unused modules
memory_optimizer.cleanup_modules(['pandas', 'numpy'])

# Optimize dictionaries
optimized_dict = memory_optimizer.optimize_dict(large_dict)

# Stop optimization thread when shutting down
memory_optimizer.stop_optimization()
```

### 6. Signal Processing Logic

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

### 7. File-Based Storage

The `file_storage.py` provides a lightweight alternative to database storage:

- JSON file-based persistence
- Token management with expiration handling
- Settings storage with defaults
- Thread-safe operations

### 8. Optimized Notification System

The Telegram notification system has been optimized for better user experience:

- **Combined Alert & Trade Notifications**: ChartInk alerts and the corresponding trade executions are combined into a single notification message rather than sending separate messages
- **Selective Notifications**: Login notifications are disabled to reduce notification noise while critical system notifications (token expiry, market status) are preserved
- **Customizable Notification Settings**: User can enable/disable specific notification types through settings
- **Rich Notification Format**: Notifications include emojis, formatting, and clickable links for better readability
- **End-of-Day Summaries**: Automatic daily trading summaries with P&L analysis

Example of combined notification format:
```
🟢 ChartInk BUY Alert with Orders

Scan: Short term breakouts
Time: 2025-04-01 10:45:32

Orders Placed: 2 of 3
Total Value: ₹9500.00

Trades:
- STOCK1: BUY 25 @ ₹200.00 = ₹5000.00
  Order ID: 123456789
- STOCK2: BUY 30 @ ₹150.00 = ₹4500.00
  Order ID: 987654321
```

## System Constants and Configurations

### Environmental Variables

Key configuration parameters are loaded from environment variables:

```
KITE_API_KEY          # Zerodha API key
KITE_API_SECRET       # Zerodha API secret
DEFAULT_QUANTITY      # Default order quantity
MAX_TRADE_VALUE       # Maximum value per trade
API_RATE_LIMIT        # API calls per second (default: 3)
PORT                  # Server port (default: 5000)
BYPASS_MARKET_HOURS   # Testing flag to bypass market hours check
MINIMAL_MODE          # Flag for running in minimal mode
TELEGRAM_BOT_TOKEN    # Telegram bot token for notifications
TELEGRAM_CHAT_ID      # Telegram chat ID for receiving notifications
```

### Railway Deployment Optimization

The application is optimized for Railway deployment with:

- Minimal resource usage during market closed hours
- Adaptive sleep strategies to reduce CPU usage
- Worker and thread count optimized for memory efficiency
- Automatic garbage collection to prevent memory leaks
- Module unloading to free memory when not needed

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
6. Position size is calculated based on Maximum Trade Value (per stock limit)
7. Stocks with prices higher than Maximum Trade Value are skipped
8. Market order is placed with delivery (CNC) order type
9. Trade details are logged and consolidated notifications sent
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
4. ✅ **Token Expiration Handling**: Added centralized token management with accurate 6 AM IST expiration detection, clear user notifications, and token status dashboard
5. ✅ **Railway Environment Optimization**: Implemented memory optimization with adaptive resource usage, garbage collection, and module unloading to reduce costs on Railway
6. ✅ **Simplified Trading Logic**: Streamlined position sizing to use only Maximum Trade Value per stock, with no automatic stop losses
7. ✅ **Enhanced Error Handling**: Improved error handling throughout the application with robust fallbacks and sensible defaults
8. ✅ **Optimized Notification System**: Disabled login notifications and combined ChartInk alerts with trade notifications for a cleaner notification experience
9. ✅ **Dashboard Improvements**: Enhanced the trading dashboard with better error handling and data display

## Maintenance and Operations Guide

### Daily Operations

1. **Token Renewal**: The Zerodha API token expires daily at 6 AM IST. The system will automatically notify when the token is about to expire during market hours.
2. **Monitoring**: Check the dashboard for active positions, P&L, and any error messages.
3. **End-of-Day Summary**: A trading summary is automatically sent at market close (3:30 PM IST) via Telegram.

### Updating the System

1. **Code Updates**: Pull the latest code and restart the application.
2. **Configuration Changes**: Update environment variables as needed.
3. **Trade Settings**: Modify DEFAULT_QUANTITY and MAX_TRADE_VALUE through the settings page.

## Conclusion

The Kite Trading Bot provides a robust, automated trading solution that integrates with ChartInk for technical analysis signals and Zerodha's Kite API for order execution. The system has been optimized for reliability, resource efficiency, and user experience with features like rate limiting, market status awareness, memory optimization, and intelligent notifications.

The latest improvements to the notification system ensure that users receive only critical alerts while combining related notifications to reduce clutter. The system is now more stable with enhanced error handling throughout the application.

Future development could focus on:
1. **Advanced Trading Strategies**: Implement more sophisticated entry/exit rules and risk management
2. **Machine Learning Integration**: Add ML-based signal filtering to improve trade quality
3. **Extended Analytics**: Enhance P&L reporting and performance metrics
4. **Multi-User Support**: Enable multiple trading accounts and user profiles

This project demonstrates effective integration of multiple technical systems (APIs, webhooks, notification systems) while maintaining operational efficiency and resource optimization suitable for cloud deployment.

## For AI Developers

When making modifications to this codebase, consider:

1. **Rate Limiting**: All API interactions should go through the rate-limited client
2. **Market Hours**: Trading logic should check market status before executing trades
3. **Error Handling**: API errors should be caught and handled appropriately 
4. **Logging**: Maintain detailed logging for troubleshooting
5. **Dependencies**: Use lazy imports for any cross-module dependencies that could become circular
6. **Memory Usage**: Leverage the memory optimizer for resource-intensive operations
7. **Token Management**: Use the token manager for all token-related operations
8. **Notification Strategy**: Follow the established pattern of providing only necessary notifications
9. **User Experience**: Always consider the end-user experience when implementing new features 