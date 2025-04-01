#!/usr/bin/env python
"""
File Storage Module

Simple file-based storage for tokens and settings instead of using a database.
Uses JSON files to persist data with backup locations for Railway's ephemeral filesystem.
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
    """File-based storage implementation using JSON files with backup locations"""
    
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
        
        # Main storage locations
        self.token_file = os.path.join(data_dir, "token.json")
        self.settings_file = os.path.join(data_dir, "settings.json")
        
        # Backup locations in case Railway's ephemeral filesystem loses the data directory
        self.tmp_dir = "/tmp" if os.path.exists("/tmp") else os.environ.get("TEMP", "tmp")
        self.backup_token_file = os.path.join(self.tmp_dir, "token_backup.json")
        self.backup_settings_file = os.path.join(self.tmp_dir, "settings_backup.json")
        
        # Ensure backup directory exists
        try:
            if not os.path.exists(self.tmp_dir):
                os.makedirs(self.tmp_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating backup directory: {e}")
            
        # Create default settings if they don't exist
        self._ensure_default_settings()
    
    def _ensure_default_settings(self):
        """Ensure default settings exist"""
        if not self.get_all_settings():
            default_settings = {
                'DEFAULT_QUANTITY': '1',
                'MAX_TRADE_VALUE': '5000',
                'TELEGRAM_ENABLED': 'true'
            }
            self.update_settings(default_settings)
            logger.info("Created default settings file")
    
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
        
        # Try to write to primary location
        success = False
        try:
            with open(self.token_file, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Saved token for user {username} (expires in {expires_in_hours} hours)")
            success = True
        except Exception as e:
            logger.error(f"Error writing token to primary file: {e}")
        
        # Always try to write backup
        try:
            with open(self.backup_token_file, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Saved backup token for user {username}")
            success = True
        except Exception as e:
            logger.error(f"Error writing token to backup file: {e}")
        
        if not success:
            logger.critical("Failed to save token to any location!")
        
        return token_data
    
    def get_token(self):
        """
        Get the saved access token if it exists and is valid
        
        Returns:
            dict: Token data or None if not found or expired
        """
        # First try primary location
        token_data = None
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    token_data = json.load(f)
                logger.info("Loaded token from primary location")
            except Exception as e:
                logger.error(f"Error reading token from primary location: {e}")
        
        # If primary failed, try backup
        if token_data is None and os.path.exists(self.backup_token_file):
            try:
                with open(self.backup_token_file, "r") as f:
                    token_data = json.load(f)
                logger.info("Loaded token from backup location")
                
                # If we successfully read from backup, try to restore primary
                try:
                    with open(self.token_file, "w") as f:
                        json.dump(token_data, f, indent=2)
                    logger.info("Restored primary token file from backup")
                except Exception as e:
                    logger.error(f"Failed to restore primary token from backup: {e}")
            except Exception as e:
                logger.error(f"Error reading token from backup location: {e}")
        
        # If token is still None, we couldn't find it anywhere
        if token_data is None:
            logger.warning("No token file found in any location")
            return None
        
        # Check if token is expired
        if "expires_timestamp" in token_data:
            now_timestamp = time.time()
            if now_timestamp > token_data["expires_timestamp"]:
                logger.warning("Token has expired")
                return None
        
        return token_data
    
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
        
        # Write back to files
        self.update_settings(settings)
        
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
        # Try primary location first
        settings = None
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    settings = json.load(f)
            except Exception as e:
                logger.error(f"Error reading settings from primary location: {e}")
        
        # If primary failed, try backup
        if settings is None and os.path.exists(self.backup_settings_file):
            try:
                with open(self.backup_settings_file, "r") as f:
                    settings = json.load(f)
                logger.info("Loaded settings from backup location")
                
                # If we successfully read from backup, try to restore primary
                try:
                    with open(self.settings_file, "w") as f:
                        json.dump(settings, f, indent=2)
                    logger.info("Restored primary settings file from backup")
                except Exception as e:
                    logger.error(f"Failed to restore primary settings from backup: {e}")
            except Exception as e:
                logger.error(f"Error reading settings from backup location: {e}")
        
        # If settings is still None, we couldn't find it anywhere
        if settings is None:
            logger.info("No settings file found, creating defaults")
            settings = {}
        
        return settings
    
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
        
        # Try to ensure data directory exists
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating data directory for settings: {e}")
        
        # Write to primary location
        primary_success = False
        try:
            with open(self.settings_file, "w") as f:
                json.dump(current_settings, f, indent=2)
            primary_success = True
        except Exception as e:
            logger.error(f"Error writing settings to primary location: {e}")
        
        # Always try to write backup
        backup_success = False
        try:
            with open(self.backup_settings_file, "w") as f:
                json.dump(current_settings, f, indent=2)
            backup_success = True
        except Exception as e:
            logger.error(f"Error writing settings to backup location: {e}")
        
        if primary_success or backup_success:
            logger.info(f"Updated {len(settings_dict)} settings")
        else:
            logger.critical("Failed to save settings to any location!")
    
    def clear(self):
        """Clear all stored data (for testing)"""
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
        
        if os.path.exists(self.settings_file):
            os.remove(self.settings_file)
            
        if os.path.exists(self.backup_token_file):
            os.remove(self.backup_token_file)
            
        if os.path.exists(self.backup_settings_file):
            os.remove(self.backup_settings_file)
        
        logger.info("Cleared all stored data")

# Create a global instance
storage = FileStorage() 