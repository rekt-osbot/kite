#!/usr/bin/env python
"""
File Storage Module

Simple file-based storage for tokens and settings instead of using a database.
Uses JSON files to persist data.
"""
import os
import json
import logging
from datetime import datetime, timedelta
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FileStorage:
    """File-based storage implementation using JSON files"""
    
    def __init__(self, data_dir="data"):
        """Initialize the storage with a data directory"""
        self.data_dir = data_dir
        
        # Create data directory if it doesn't exist
        try:
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
                logger.info(f"Created data directory: {data_dir}")
        except Exception as e:
            logger.error(f"Error creating data directory: {e}")
        
        # File paths
        self.token_file = os.path.join(data_dir, "token.json")
        self.settings_file = os.path.join(data_dir, "settings.json")
    
    def save_token(self, user_id, username, access_token, expires_in_hours=24):
        """
        Save access token to file storage
        
        Args:
            user_id (str): User ID from Zerodha
            username (str): Username from Zerodha
            access_token (str): The access token to save
            expires_in_hours (int): Hours until token expiration
            
        Returns:
            dict: Token data with expiration info
        """
        now = datetime.now()
        expires_at = now + timedelta(hours=expires_in_hours)
        
        # Create token data
        token_data = {
            "user_id": user_id,
            "username": username,
            "access_token": access_token,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_timestamp": time.mktime(expires_at.timetuple())
        }
        
        # Ensure data directory exists
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir, exist_ok=True)
                logger.info(f"Created data directory before saving token: {self.data_dir}")
        except Exception as e:
            logger.error(f"Error creating data directory for token: {e}")
        
        # Write to file
        try:
            with open(self.token_file, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Saved token for user {username} (expires in {expires_in_hours} hours)")
        except Exception as e:
            logger.error(f"Error writing token to file: {e}")
        
        return token_data
    
    def get_token(self):
        """
        Get the saved access token if it exists and is valid
        
        Returns:
            dict: Token data or None if not found or expired
        """
        if not os.path.exists(self.token_file):
            logger.warning("No token file found")
            return None
        
        try:
            with open(self.token_file, "r") as f:
                token_data = json.load(f)
            
            # Check if token is expired
            if "expires_timestamp" in token_data:
                now_timestamp = time.time()
                if now_timestamp > token_data["expires_timestamp"]:
                    logger.warning("Token has expired")
                    return None
            
            return token_data
        
        except Exception as e:
            logger.error(f"Error reading token: {e}")
            return None
    
    def set_setting(self, key, value):
        """
        Save a setting to file storage
        
        Args:
            key (str): Setting key
            value (str): Setting value
        """
        # Load existing settings
        settings = self.get_all_settings()
        
        # Update with new value
        settings[key] = value
        
        # Write back to file
        with open(self.settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        
        logger.info(f"Updated setting: {key}")
    
    def get_setting(self, key, default=None):
        """
        Get a setting value
        
        Args:
            key (str): Setting key
            default: Default value if not found
            
        Returns:
            Value of the setting or default if not found
        """
        settings = self.get_all_settings()
        return settings.get(key, default)
    
    def get_all_settings(self):
        """
        Get all settings as a dictionary
        
        Returns:
            dict: All settings
        """
        if not os.path.exists(self.settings_file):
            return {}
        
        try:
            with open(self.settings_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading settings: {e}")
            return {}
    
    def update_settings(self, settings_dict):
        """
        Update multiple settings at once
        
        Args:
            settings_dict (dict): Dictionary of settings to update
        """
        # Load existing settings
        current_settings = self.get_all_settings()
        
        # Update with new values
        current_settings.update(settings_dict)
        
        # Write back to file
        with open(self.settings_file, "w") as f:
            json.dump(current_settings, f, indent=2)
        
        logger.info(f"Updated {len(settings_dict)} settings")
    
    def clear(self):
        """Clear all stored data (for testing)"""
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
        
        if os.path.exists(self.settings_file):
            os.remove(self.settings_file)
        
        logger.info("Cleared all stored data")

# Create a global instance
storage = FileStorage() 