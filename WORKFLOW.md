# ChartInk-Zerodha Integration Workflow

This document explains the complete workflow for setting up and using the ChartInk-Zerodha integration, from registration to automated trading.

## Setup Workflow

### 1. Zerodha Registration and API Setup

1. **Register a Zerodha Developer App**:
   - Go to [Zerodha Developer Console](https://developers.kite.trade/)
   - Login with your Zerodha credentials
   - Click "Create an App"
   - Fill in the details:
     - **App Name**: [YOUR_APP_NAME]
     - **Redirect URL**: `[YOUR_REDIRECT_URL]`
     - Leave other fields as default
   - Submit the form

2. **Get API Credentials**:
   - After app creation, note down:
     - **API Key**: [YOUR_API_KEY]
     - **API Secret**: [YOUR_API_SECRET]

### 2. Railway Deployment Setup

1. **Prepare Your Repository**:
   - Clone/download this project
   - Create a GitHub repository and push the code
   - Make sure you have:
     - `kite_connect.py`
     - `chartink_webhook.py`
     - `telegram_notifier.py`
     - `Procfile`
     - `requirements.txt`
     - Other supporting files

2. **Deploy to Railway**:
   - Register at [Railway.app](https://railway.app/)
   - Create a new project → "Deploy from GitHub"
   - Select your repository
   - Once deployed, your app URL will be: `[YOUR_APP_URL]`

3. **Set Environment Variables**:
   - Create a `.env` file with these variables:
     ```
     KITE_API_KEY=[YOUR_API_KEY]
     KITE_API_SECRET=[YOUR_API_SECRET]
     KITE_ACCESS_TOKEN=[YOUR_ACCESS_TOKEN]
     DEFAULT_QUANTITY=[DEFAULT_QUANTITY]
     MAX_TRADE_VALUE=[MAX_TRADE_VALUE]
     STOP_LOSS_PERCENT=[STOP_LOSS_PERCENT]
     TARGET_PERCENT=[TARGET_PERCENT]
     MAX_POSITION_SIZE=[MAX_POSITION_SIZE]
     PORT=[PORT]
     DEBUG=[DEBUG_MODE]
     APP_URL=[YOUR_APP_URL]
     REDIRECT_URL=[YOUR_REDIRECT_URL]
     TELEGRAM_BOT_TOKEN=[YOUR_TELEGRAM_BOT_TOKEN]
     TELEGRAM_CHAT_ID=[YOUR_TELEGRAM_CHAT_ID]
     ```
   - Upload these variables to Railway either via the web interface or CLI

4. **Update Zerodha Redirect URL**:
   - Ensure your Zerodha app's Redirect URL is set to:
   - `[YOUR_REDIRECT_URL]`

### 3. Telegram Setup (Optional)

1. **Create a Telegram Bot**:
   - Open Telegram and search for "@BotFather"
   - Start a chat and send "/newbot" command
   - Follow instructions to create a bot
   - Get the bot token (looks like "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")

2. **Get Your Chat ID**:
   - Option 1: Open Telegram and search for "@userinfobot"
   - Start a chat and it will display your chat ID
   - 
   - Option 2: For channels, use the channel username with @ prefix (e.g., "@mychannel")

3. **Configure Telegram Settings**:
   - Add your bot token and chat ID to the environment variables
   - Or configure them via the Settings page in the app

### 4. Initial Token Authentication

1. **Access Your App**:
   - Open [YOUR_APP_URL](https://your-app-url/) in your browser
   - You'll see the dashboard page

2. **Authenticate with Zerodha**:
   - If not authenticated, click "Authentication" in the top menu
   - Click "Login to Zerodha"
   - You'll be redirected to Zerodha's login page
   - Login with your Zerodha credentials
   - Authorize the app
   - You'll be redirected back to your app
   - The page should now show "Currently logged in as: [Your Name]"
   - This means the access token has been successfully generated and stored

### 5. ChartInk Configuration

1. **Create a Scanner in ChartInk**:
   - Login to [ChartInk](https://chartink.com/)
   - Create or select a scanner with your desired criteria

2. **Set Up Webhook Alert**:
   - Click "Create/Modify Alert" below the scanner
   - In the alert settings, find the webhook URL field
   - Enter: `[YOUR_WEBHOOK_URL]`
   - Set other alert parameters as needed
   - Save the alert

## Operational Workflow

### 1. Daily Authentication Process

1. **Token Expiry**:
   - Zerodha tokens expire at 6 AM IST every day
   - The app checks token validity periodically
   - You'll receive a notification via Telegram if configured

2. **Manual Refresh**:
   - Visit [YOUR_APP_URL/auth/refresh](https://your-app-url/auth/refresh)
   - Click "Login to Zerodha"
   - Complete the Zerodha login flow
   - Your token is now refreshed for the day

### 2. Using the Dashboard

1. **Viewing Positions and Orders**:
   - Visit [YOUR_APP_URL](https://your-app-url/)
   - The dashboard shows current positions, P&L, available margin, and orders
   - Use the refresh buttons to update data in real-time

2. **Viewing ChartInk Alerts**:
   - Click "Alerts" in the navigation
   - This page displays all ChartInk alerts received today
   - Alerts are color-coded (green for buy signals, red for sell signals)
   - Each alert shows the scanner name, triggered time, and list of stocks with prices

3. **Configuring Trading Settings**:
   - Click "Settings" in the navigation
   - Modify trading parameters:
     - Default Quantity: The default number of shares to trade
     - Maximum Trade Value: The maximum rupee value per trade
     - Stop Loss Percentage: The percentage below buy price for stop loss
     - Target Percentage: The percentage above buy price for targets
   - Configure Telegram notifications:
     - Bot Token: Your Telegram bot token
     - Chat ID: Your chat ID or channel name
     - Test button: Verify your Telegram configuration

### 3. Trading Process

1. **ChartInk Alert Trigger**:
   - When your ChartInk scanner detects matching stocks
   - It sends a webhook POST request to your app

2. **Webhook Processing**:
   - Your app receives the webhook data
   - Format:
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
   - The alert is logged and displayed on the Alerts page
   - A notification is sent to Telegram (if configured)

3. **Available Funds Check**:
   - System checks if there are sufficient funds in your Zerodha account
   - If funds are insufficient, the alert is logged but no orders are placed
   - A notification is sent to Telegram about insufficient funds

4. **Transaction Type Determination**:
   - The app looks at the scan name to determine buy/sell
   - Buys if scan name contains: "buy", "bullish", "breakout"
   - Sells if scan name contains: "sell", "bearish", "short"

5. **Order Execution**:
   - For each stock in the alert:
     1. **Position Sizing**: Calculates quantity based on `MAX_POSITION_SIZE` and available funds
     2. **CNC Orders**: Uses delivery (CNC) order type for all trades
     3. **Stop-Loss Only**: For buy orders, places only stop-loss sell orders (no target orders)
     4. Logs the trade details and sends execution notification to Telegram

6. **Trade Management**:
   - Stop-loss orders handle risk management automatically
   - You manually manage taking profits (no automatic target orders)
   - You can monitor positions and orders in your app dashboard or Zerodha account

## Notifications

1. **Telegram Notifications**:
   - Authentication status changes
   - ChartInk alerts received
   - Trade executions
   - Stop loss order placements
   - Insufficient funds warnings

2. **Web Dashboard**:
   - Realtime trade status
   - Current positions and P&L
   - Order history
   - Alert history

## Data Flow Diagram