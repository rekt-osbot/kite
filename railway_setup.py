import os
import subprocess
import sys
from migrations import init_database

def main():
    """Set up the Railway PostgreSQL database and initialize tables"""
    print("Setting up Railway PostgreSQL database...")
    
    # Verify DATABASE_URL is available
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("Please set up a PostgreSQL database on Railway and link it to this service.")
        sys.exit(1)
    
    print("Database URL found. Creating database tables...")
    
    try:
        # Initialize database tables
        init_database()
        print("Database setup completed successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 