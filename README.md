# Zerodha Kite API Integration with ChartInk

This project connects to Zerodha Kite API to fetch user profile, margin details, order history, and current positions. It includes a complete trading dashboard, alerts tracking, and a webhook server that receives ChartInk scanner alerts and automatically executes trades.

## Features

- **Complete Trading Dashboard** - Monitor positions, orders, and account balances
- **Alerts Tracking** - View ChartInk alerts history with formatting for buy/sell signals
- **Settings Management** - Configure trading parameters and notification settings
- **Telegram Notifications** - Receive instant alerts for trades, signals, and authentication status
- **Authentication System** - Login, token management, and session handling
- **Automated Trading** - Execute trades automatically based on ChartInk alerts
- **Order Management** - Place orders with stop-loss and target levels
- **Enhanced Signal Detection** - Advanced keyword detection for buy/sell signals

## Setup

### Local Development

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Ensure your `.env` file has the required API credentials:
   ```
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
   KITE_ACCESS_TOKEN=
   
   # Trading Parameters
   DEFAULT_QUANTITY=1
   MAX_TRADE_VALUE=5000
   STOP_LOSS_PERCENT=2
   TARGET_PERCENT=4
   
   # Server Configuration
   PORT=5000
   DEBUG=True
   
   # For Railway Deployment
   APP_URL=https://your-railway-app-url.up.railway.app
   REDIRECT_URL=https://your-railway-app-url.up.railway.app/auth/redirect
   
   # Telegram Notifications (Optional)
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   
   # Optional: Backup Notification (ntfy.sh)
   NTFY_TOPIC=your-notification-channel
   ```

   You need to obtain your API key and secret from the [Zerodha Kite Developer Console](https://kite.trade/).

3. For Telegram notifications:
   - Create a Telegram bot via [BotFather](https://t.me/BotFather)
   - Get your chat ID (use [@userinfobot](https://t.me/userinfobot) or create a group and add [@RawDataBot](https://t.me/RawDataBot))
   - Add the bot token and chat ID to your .env file

### Railway Deployment

1. Sign up at [railway.app](https://railway.app) (free tier available)

2. Create a new project:
   - Go to Railway dashboard
   - Click "New Project" → "Deploy from GitHub"
   - Connect your GitHub repository

3. Set Environment Variables:
   - Go to your project settings → "Variables"
   - Add all the environment variables from your .env file
   - Make sure to set:
     - `APP_URL`: Your Railway app URL
     - `REDIRECT_URL`: Your Railway app URL + "/auth/redirect"
     - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (if using Telegram)

4. Set Up PostgreSQL Database:
   - In your Railway project, click "+ New"
   - Select "Database" → "PostgreSQL"
   - Wait for the database to provision
   - The `DATABASE_URL` environment variable will automatically be added to your project
   - See [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed instructions

5. Set Up Zerodha App:
   - Go to [Zerodha Developer Console](https://developers.kite.trade/apps)
   - Create a new app or edit your existing one
   - Set the Redirect URL to match your `REDIRECT_URL` (https://your-railway-app-url.up.railway.app/auth/redirect)

6. First-time Token Authentication:
   - Open your Railway app URL in a browser
   - Click "Login to Zerodha" and follow the authentication process
   - After successful authentication, your webhook is ready to receive ChartInk alerts
   - The authentication token will be stored in the database and will persist for 24 hours

## Usage

### Dashboard and Web Interface

Once deployed (or running locally), you can access the full application at your app URL:

- **Dashboard** (`/` or `/auth/dashboard.html`) - View positions, orders, and account balances
- **Alerts** (`/auth/alerts.html`) - Track ChartInk alert history
- **Settings** (`/auth/settings.html`) - Configure trading and notification parameters
- **Authentication** (`/auth/refresh.html`) - Login to Zerodha and manage tokens

### Setting up ChartInk

1. Create a scanner in ChartInk
2. Set up a webhook to your server:
   - Go to your scanner and click "Create/Modify Alert" 
   - In the webhook URL field, enter: 
     - For local testing with ngrok: `http://your-ngrok-url/webhook`
     - For Railway deployment: `https://your-railway-app-url.up.railway.app/webhook`
   - Make sure your server is accessible from the internet

ChartInk will send alerts in the following format:
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

### Advanced Signal Detection

The application automatically determines whether to buy or sell based on keywords in the scan and alert names. Recognized keywords include:

**Buy Keywords**: "buy", "bull", "bullish", "long", "breakout", "up", "uptrend", "support", "bounce", "reversal", "upside"

**Sell Keywords**: "sell", "bear", "bearish", "short", "breakdown", "down", "downtrend", "resistance", "fall", "decline"

You can also explicitly set the action by including `"action":"BUY"` or `"action":"SELL"` in your webhook payload.

### Token Refresh

Zerodha tokens expire at 6 AM IST every day. To refresh your token:

1. **Web Interface**
   - Visit the authentication page at `/auth/refresh.html`
   - Click "Login to Zerodha" button
   - Complete the Zerodha login flow
   - Your token will be updated and ready to use

2. **Automatic Notification**
   - You'll receive a Telegram notification when your token expires
   - Click the link in the notification to refresh your token

## Testing the Webhook

You can simulate ChartInk alerts using tools like Postman or curl:

```bash
curl -X POST https://your-app-url/webhook \
  -H "Content-Type: application/json" \
  -d '{"stocks":"RELIANCE,INFY,TCS","trigger_prices":"2500,1800,3500","scan_name":"Bullish Breakout","triggered_at":"3:45 pm","alert_name":"Breakout Alert"}'
```

## Next Steps

See [NEXT_STEPS.md](NEXT_STEPS.md) for the planned enhancements and future roadmap.

## Documentation

- For more information about the Zerodha Kite API, refer to:
  https://kite.trade/docs/connect/v3/
  
- For information about ChartInk webhooks, visit:
  https://chartink.com/articles/alerts/webhook-support-for-alerts/
  
- For Telegram Bot API documentation:
  https://core.telegram.org/bots/api 