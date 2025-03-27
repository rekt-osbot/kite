# ChartInk-Zerodha Integration Workflow

This document explains the complete workflow for setting up and using the ChartInk-Zerodha integration, from registration to automated trading.

## Setup Workflow

### 1. Zerodha Registration and API Setup

1. **Register a Zerodha Developer App**:
   - Go to [Zerodha Developer Console](https://developers.kite.trade/)
   - Login with your Zerodha credentials
   - Click "Create an App"
   - Fill in the details:
     - **App Name**: CGTrades
     - **Redirect URL**: `https://kite-project-production.up.railway.app/auth/redirect`
     - Leave other fields as default
   - Submit the form

2. **Get API Credentials**:
   - After app creation, note down:
     - **API Key**: zx6rwc52fvhexvjo
     - **API Secret**: r9ggy73bjw7j2khe4sa5kmey6qyr8u47

### 2. Railway Deployment Setup

1. **Prepare Your Repository**:
   - Clone/download this project
   - Create a GitHub repository and push the code
   - Make sure you have:
     - `kite_connect.py`
     - `chartink_webhook.py`
     - `Procfile`
     - `requirements.txt`
     - Other supporting files

2. **Deploy to Railway**:
   - Register at [Railway.app](https://railway.app/)
   - Create a new project → "Deploy from GitHub"
   - Select your repository
   - Once deployed, your app URL will be: `https://kite-project-production.up.railway.app`

3. **Set Environment Variables**:
   - Create a `.env` file with these variables:
     ```
     KITE_API_KEY=zx6rwc52fvhexvjo
     KITE_API_SECRET=r9ggy73bjw7j2khe4sa5kmey6qyr8u47
     KITE_ACCESS_TOKEN=Sr7h40VOCOj7XM1NF3C4qq4ONz0DDrjr
     DEFAULT_QUANTITY=1
     MAX_TRADE_VALUE=5000
     STOP_LOSS_PERCENT=2
     TARGET_PERCENT=4
     PORT=5000
     DEBUG=False
     APP_URL=https://kite-project-production.up.railway.app
     REDIRECT_URL=https://kite-project-production.up.railway.app/auth/redirect
     ```
   - Upload these variables to Railway either via the web interface or CLI

4. **Update Zerodha Redirect URL**:
   - Ensure your Zerodha app's Redirect URL is set to:
   - `https://kite-project-production.up.railway.app/auth/redirect`

### 3. Initial Token Authentication

1. **Access Your App**:
   - Open [https://kite-project-production.up.railway.app/](https://kite-project-production.up.railway.app/) in your browser
   - You'll see the auth/refresh page

2. **Authenticate with Zerodha**:
   - Click "Login to Zerodha"
   - You'll be redirected to Zerodha's login page
   - Login with your Zerodha credentials
   - Authorize the app
   - You'll be redirected back to your app
   - The page should now show "Currently logged in as: [Your Name]"
   - This means the access token has been successfully generated and stored

### 4. ChartInk Configuration

1. **Create a Scanner in ChartInk**:
   - Login to [ChartInk](https://chartink.com/)
   - Create or select a scanner with your desired criteria

2. **Set Up Webhook Alert**:
   - Click "Create/Modify Alert" below the scanner
   - In the alert settings, find the webhook URL field
   - Enter: `https://kite-project-production.up.railway.app/webhook`
   - Set other alert parameters as needed
   - Save the alert

## Operational Workflow

### Daily Authentication Process

1. **Token Expiry**:
   - Zerodha tokens expire at 6 AM IST every day
   - The app checks token validity periodically

2. **Manual Refresh**:
   - Visit [https://kite-project-production.up.railway.app/](https://kite-project-production.up.railway.app/)
   - Click "Login to Zerodha"
   - Complete the Zerodha login flow
   - Your token is now refreshed for the day

### Trading Process

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

3. **Transaction Type Determination**:
   - The app looks at the scan name to determine buy/sell
   - Buys if scan name contains: "buy", "bullish", "breakout"
   - Sells if scan name contains: "sell", "bearish", "short"

4. **Order Execution**:
   - For each stock in the alert:
     1. Calculates quantity based on price and `MAX_TRADE_VALUE` (5000 INR)
     2. Places order through Zerodha Kite API
     3. For buy orders:
        - Places stop-loss order at `price * (1 - STOP_LOSS_PERCENT/100)` (2% below price)
        - Places target order at `price * (1 + TARGET_PERCENT/100)` (4% above price)
     4. Logs the trade to `trade_log.json`

5. **Trade Management**:
   - Stop-loss and target orders handle risk management automatically
   - You can monitor positions and orders in your Zerodha account

## Data Flow Diagram

```
┌─────────────┐    Scanner Alert    ┌───────────────────────────┐      Order      ┌─────────────┐
│   ChartInk  │──────Webhook───────▶│  kite-project-production  │───Placement────▶│   Zerodha   │
│   Scanner   │                     │      .up.railway.app      │                 │    Kite     │
└─────────────┘                     └───────────────────────────┘                 └─────────────┘
                                              ▲                                         ▲
                                              │                                         │
                                              │                                         │
                                     Token    │                                         │   Authentication
                                  Refresh     │                                         │
                                              │                                         │
                                              │                                         │
                                        ┌─────┴──────┐                                  │
                                        │    You     │──────────────────────────────────┘
                                        │  (Browser) │    Login
                                        └────────────┘
```

## Troubleshooting

1. **Authentication Failures**:
   - Check if the `REDIRECT_URL` in your environment variables matches exactly with what's set in Zerodha Developer Console
   - Ensure the API key and secret are correctly copied
   - Current redirect URL: `https://kite-project-production.up.railway.app/auth/redirect`

2. **Webhook Not Working**:
   - Verify your ChartInk alert has the correct webhook URL: `https://kite-project-production.up.railway.app/webhook`
   - Check if your access token is valid (visit your app URL to confirm)
   - Look at the logs in Railway dashboard for any errors

3. **Orders Not Executing**:
   - Ensure you have sufficient funds in your Zerodha account
   - Check if the market is open (orders won't execute during market closure)
   - Verify the trading symbols from ChartInk match Zerodha's format

## Current Configuration

Your system is deployed with the following configuration:

1. **Deployment URL**: https://kite-project-production.up.railway.app/
2. **Zerodha API Key**: zx6rwc52fvhexvjo
3. **Default Trading Parameters**:
   - Default Quantity: 1
   - Max Trade Value: 5000 INR
   - Stop Loss: 2%
   - Target: 4% 