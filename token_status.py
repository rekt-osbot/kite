#!/usr/bin/env python
"""
Token Status Module

Provides a web endpoint to display token status information,
including expiration time and trading status.
"""
import os
import logging
from datetime import datetime
import pytz
from flask import Flask, render_template_string, jsonify
from token_manager import token_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

# HTML template for token status page
TOKEN_STATUS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zerodha Token Status - Kite Trading Bot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
            background-color: #f9f9f9;
            margin-top: 20px;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
        }
        .status-card {
            margin: 20px 0;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-valid {
            background-color: #d5f5e3;
            border-left: 4px solid #2ecc71;
        }
        .status-warning {
            background-color: #fef9e7;
            border-left: 4px solid #f1c40f;
        }
        .status-expired {
            background-color: #fadbd8;
            border-left: 4px solid #e74c3c;
        }
        .status-header {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        .status-icon {
            font-size: 24px;
            margin-right: 10px;
        }
        .status-title {
            font-size: 18px;
            font-weight: bold;
            margin: 0;
        }
        .info-row {
            display: flex;
            margin: 8px 0;
        }
        .info-label {
            width: 40%;
            font-weight: bold;
        }
        .info-value {
            width: 60%;
        }
        .actions {
            margin-top: 20px;
            text-align: center;
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .btn:hover {
            background-color: #2980b9;
        }
        .market-hours {
            margin-top: 30px;
            background-color: #eaecee;
            padding: 15px;
            border-radius: 5px;
        }
        .refresh {
            text-align: center;
            margin-top: 15px;
            font-size: 0.8em;
            color: #7f8c8d;
        }
        .timestamp {
            text-align: right;
            font-size: 0.8em;
            color: #95a5a6;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>Zerodha Token Status</h1>
    
    <div class="container">
        {% if status.authenticated %}
            {% if status.expires_during_market_hours %}
                <div class="status-card status-warning">
                    <div class="status-header">
                        <div class="status-icon">⚠️</div>
                        <h2 class="status-title">Token Valid - Expires During Market Hours</h2>
                    </div>
                    <p>Your token is currently valid but will expire at 6 AM IST during market hours.</p>
                </div>
            {% else %}
                <div class="status-card status-valid">
                    <div class="status-header">
                        <div class="status-icon">✅</div>
                        <h2 class="status-title">Token Valid</h2>
                    </div>
                    <p>Your Zerodha API token is active and trading is enabled.</p>
                </div>
            {% endif %}
        {% else %}
            <div class="status-card status-expired">
                <div class="status-header">
                    <div class="status-icon">❌</div>
                    <h2 class="status-title">Token Expired</h2>
                </div>
                <p>Your Zerodha API token has expired. Trading operations are disabled.</p>
            </div>
        {% endif %}
        
        <div class="info-row">
            <div class="info-label">Username:</div>
            <div class="info-value">{{ status.username or 'Not logged in' }}</div>
        </div>
        
        <div class="info-row">
            <div class="info-label">Trading Status:</div>
            <div class="info-value">
                {% if status.trading_enabled %}
                    <span style="color: #27ae60; font-weight: bold;">Enabled</span>
                {% else %}
                    <span style="color: #c0392b; font-weight: bold;">Disabled</span>
                {% endif %}
            </div>
        </div>
        
        <div class="info-row">
            <div class="info-label">Current Time:</div>
            <div class="info-value">{{ status.current_time }}</div>
        </div>
        
        {% if status.authenticated %}
            <div class="info-row">
                <div class="info-label">Token Expires At:</div>
                <div class="info-value">{{ status.expires_at }}</div>
            </div>
            
            <div class="info-row">
                <div class="info-label">Hours Until Expiry:</div>
                <div class="info-value">{{ status.hours_until_expiry }} hours</div>
            </div>
            
            <div class="info-row">
                <div class="info-label">Trading Day Status:</div>
                <div class="info-value">{{ status.trading_day_status }}</div>
            </div>
        {% endif %}
        
        <div class="actions">
            <a href="/auth/refresh" class="btn">
                {% if status.authenticated %}
                    Renew Token
                {% else %}
                    Login with Zerodha
                {% endif %}
            </a>
        </div>
    </div>
    
    <div class="market-hours">
        <h3>Zerodha API Token Information:</h3>
        <ul>
            <li>Tokens expire daily at 6:00 AM IST regardless of when they were created</li>
            <li>Market hours are 9:00 AM to 3:30 PM IST (Monday to Friday)</li>
            <li>If your token expires during market hours (6 AM), you will need to renew it before expiry</li>
            <li>The trading bot will automatically disable trading if the token expires</li>
        </ul>
    </div>
    
    <div class="refresh">
        This page automatically refreshes every 5 minutes. <a href="/token/status">Refresh Now</a>
    </div>
    
    <div class="timestamp">
        Last updated: {{ status.current_time }}
    </div>
    
    <script>
        // Auto refresh every 5 minutes
        setTimeout(function() {
            window.location.reload();
        }, 5 * 60 * 1000);
    </script>
</body>
</html>
"""

def register_token_endpoints(app):
    """Register token status endpoints with the Flask app"""
    
    @app.route('/token/status')
    def token_status_page():
        """Display token status information as a web page"""
        status = token_manager.get_status_info()
        return render_template_string(TOKEN_STATUS_HTML, status=status)
    
    @app.route('/token/status/json')
    def token_status_json():
        """Return token status information as JSON"""
        status = token_manager.get_status_info()
        return jsonify(status)
    
    logger.info("Registered token status endpoints")
    return app

if __name__ == '__main__':
    # For testing the status page directly
    app = Flask(__name__)
    app = register_token_endpoints(app)
    app.run(debug=True, port=5001) 