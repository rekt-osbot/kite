import os
from flask import Flask
from models import db

def create_app():
    """Create a Flask app instance for migrations"""
    app = Flask(__name__)
    
    # Get PostgreSQL URL from environment variable
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Local development fallback
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kite.db'
    else:
        # Ensure DATABASE_URL is compatible with SQLAlchemy
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with app
    db.init_app(app)
    
    return app

def init_database():
    """Initialize database tables"""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    init_database() 