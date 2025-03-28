from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(db.Model):
    """User model for storing user profile data"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    auth_tokens = db.relationship("AuthToken", backref="user", lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"

class AuthToken(db.Model):
    """Model for storing authentication tokens"""
    __tablename__ = "auth_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    access_token = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def is_expired(self):
        """Check if the token is expired"""
        return datetime.utcnow() > self.expires_at
    
    @classmethod
    def create_token(cls, user_id, access_token, expires_in_hours=24):
        """Create a new token with the specified expiration time"""
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        return cls(user_id=user_id, access_token=access_token, expires_at=expires_at)
    
    def __repr__(self):
        return f"<AuthToken (User: {self.user_id})>"

class Settings(db.Model):
    """Model for storing application settings"""
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value by key"""
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @classmethod
    def set_value(cls, key, value, description=None):
        """Set a setting value, creating if it doesn't exist"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = cls(key=key, value=value, description=description)
            db.session.add(setting)
    
    def __repr__(self):
        return f"<Setting {self.key}>" 