import json
import requests
import sys
import argparse
import datetime

def main():
    parser = argparse.ArgumentParser(description='Simulate a ChartInk alert webhook')
    parser.add_argument('--stocks', '-s', required=True, help='Comma-separated list of stock symbols (e.g., "RELIANCE,INFY,TCS")')
    parser.add_argument('--prices', '-p', required=True, help='Comma-separated list of prices (e.g., "2500,1800,3500")')
    parser.add_argument('--scan_name', '-n', default='Breakout Scanner', help='Scanner name')
    parser.add_argument('--webhook', '-w', default='http://localhost:5000/webhook', help='Webhook URL')
    
    args = parser.parse_args()
    
    # Validate that stocks and prices have the same length
    stocks_list = args.stocks.split(',')
    prices_list = args.prices.split(',')
    
    if len(stocks_list) != len(prices_list):
        print("Error: The number of stocks and prices must match!")
        return 1
    
    # Current time in HH:MM format
    current_time = datetime.datetime.now().strftime("%I:%M %p").lower()
    
    # Prepare the alert data in ChartInk webhook format
    alert_data = {
        'stocks': args.stocks,
        'trigger_prices': args.prices,
        'triggered_at': current_time,
        'scan_name': args.scan_name,
        'scan_url': args.scan_name.lower().replace(' ', '-'),
        'alert_name': f"Alert for {args.scan_name}"
    }
    
    print(f"Sending alert for {len(stocks_list)} stocks from scanner '{args.scan_name}'")
    print(f"Stocks: {args.stocks}")
    print(f"Prices: {args.prices}")
    
    try:
        # Send the webhook request
        response = requests.post(
            args.webhook,
            json=alert_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Print the response
        print(f"Status code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 