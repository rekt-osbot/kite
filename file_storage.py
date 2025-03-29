import os
import json
import time
from datetime import datetime, timedelta
import pytz

# Set IST timezone
IST = pytz.timezone('Asia/Kolkata')

class FileStorage:
    """
    A simple file-based storage system to replace database functionality
    for token and settings storage.
    """
    
    def __init__(self, storage_dir=None):
        """Initialize the file storage system"""
        self.storage_dir = storage_dir or os.path.join(os.getcwd(), 'data')
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize files if they don't exist
        self.token_file = os.path.join(self.storage_dir, 'token.json')
        self.settings_file = os.path.join(self.storage_dir, 'settings.json')
        
        if not os.path.exists(self.token_file):
            self._save_json(self.token_file, {})
        
        if not os.path.exists(self.settings_file):
            default_settings = {
                'DEFAULT_QUANTITY': "1",
                'MAX_TRADE_VALUE': "5000",
                'STOP_LOSS_PERCENT': "2",
                'TARGET_PERCENT': "4", 
                'MAX_POSITION_SIZE': "5000",
                'TELEGRAM_ENABLED': "true"
            }
            self._save_json(self.settings_file, default_settings)
    
    def _save_json(self, filepath, data):
        """Save data to a JSON file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_json(self, filepath):
        """Load data from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    # Token management functions
    def save_token(self, user_id, username, access_token, expires_in_hours=24):
        """Save an authentication token"""
        now = datetime.now(IST)
        expires_at = now + timedelta(hours=expires_in_hours)
        
        token_data = {
            'user_id': user_id,
            'username': username,
            'access_token': access_token,
            'created_at': now.strftime("%Y-%m-%d %H:%M:%S"),
            'expires_at': expires_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self._save_json(self.token_file, token_data)
        return token_data
    
    def get_token(self):
        """Get the current token, or None if expired"""
        token_data = self._load_json(self.token_file)
        
        if not token_data:
            return None
        
        # Check if token is expired
        now = datetime.now(IST)
        expires_at = datetime.strptime(token_data.get('expires_at', ''), "%Y-%m-%d %H:%M:%S")
        expires_at = IST.localize(expires_at)
        
        if now > expires_at:
            return None
        
        return token_data
    
    def is_token_expired(self):
        """Check if the current token is expired"""
        token = self.get_token()
        return token is None
    
    # Settings functions
    def get_setting(self, key, default=None):
        """Get a setting value"""
        settings = self._load_json(self.settings_file)
        return settings.get(key, default)
    
    def set_setting(self, key, value):
        """Set a setting value"""
        settings = self._load_json(self.settings_file)
        settings[key] = value
        self._save_json(self.settings_file, settings)
    
    def get_all_settings(self):
        """Get all settings"""
        return self._load_json(self.settings_file)
    
    def update_settings(self, settings_dict):
        """Update multiple settings at once"""
        current_settings = self._load_json(self.settings_file)
        current_settings.update(settings_dict)
        self._save_json(self.settings_file, current_settings)

# Create a global instance for easy access
storage = FileStorage() 