# Zerodha Kite API Integration with ChartInk

This project connects to Zerodha Kite API to fetch user profile, margin details, order history, and current positions. It also includes a webhook server that receives ChartInk scanner alerts and automatically executes trades.

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
   
   # Optional: Notification (ntfy.sh)
   NTFY_TOPIC=your-notification-channel
   ```

   You need to obtain your API key and secret from the [Zerodha Kite Developer Console](https://kite.trade/).

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

4. Set Up Zerodha App:
   - Go to [Zerodha Developer Console](https://developers.kite.trade/apps)
   - Create a new app or edit your existing one
   - Set the Redirect URL to match your `REDIRECT_URL` (https://your-railway-app-url.up.railway.app/auth/redirect)

5. First-time Token Authentication:
   - Open your Railway app URL in a browser
   - Click "Login to Zerodha" and follow the authentication process
   - After successful authentication, your webhook is ready to receive ChartInk alerts

## Usage

### Kite Connection

When running locally, you can use the command-line interface:
```
python kite_connect.py
```

The script will:
1. Check if you're already authenticated with a valid access token
2. If not, it will open the Zerodha login page in your browser
3. After login, you need to paste the redirect URL back into the console
4. The script will then fetch and display your profile information, margin details, positions, and order history

### ChartInk Webhook Server

Run the webhook server:
```
python chartink_webhook.py
```

The server will:
1. Start a Flask server on the port specified in your `.env` file
2. Check if a valid Kite API token exists
3. Start a scheduler to periodically validate the token
4. Listen for incoming webhook alerts from ChartInk
5. Process alerts and execute trades based on the alert data

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

The script automatically determines whether to buy or sell based on the scan name. If the scan name contains words like "buy" or "breakout", it will place buy orders. If it contains words like "sell", "short", or "bearish", it will place sell orders.

### Token Refresh

Zerodha tokens expire at 6 AM IST every day. To refresh your token:

1. **Web Interface (Recommended)**
   - Visit your app URL (for Railway deployment) or http://localhost:5000 (for local development)
   - Click "Login to Zerodha" button
   - Complete the Zerodha login flow
   - Your token will be updated and ready to use

2. **Automatic Notification**
   - If you set up the NTFY_TOPIC environment variable
   - You'll receive a notification when your token expires
   - Click the link in the notification to refresh your token

### Testing the Webhook

You can simulate ChartInk alerts using the included script:
```
python simulate_chartink_alert.py --stocks "RELIANCE,INFY,TCS" --prices "2500,1800,3500" --scan_name "Bullish Breakout"
```

This will send a test alert to your webhook server with multiple stocks and their trigger prices.

## Features

- Authentication and access token generation
- Auto token validation and refresh notifications
- Web interface for one-click token refresh
- Fetching user profile information
- Retrieving margin and fund details
- Getting order history
- Fetching current positions
- Logout functionality to invalidate the session
- Webhook server for receiving ChartInk alerts
- Processing of multiple stocks in a single alert
- Automatic trade execution based on alerts
- Stop-loss and target orders for trade management
- Trade logging for tracking executed trades
- Fully deployable to Railway with minimal configuration

## Documentation

- For more information about the Zerodha Kite API, refer to:
  https://kite.trade/docs/connect/v3/
  
- For information about ChartInk webhooks, visit:
  https://chartink.com/articles/alerts/webhook-support-for-alerts/ 