# PostgreSQL Database Setup for Kite Trading App

This guide walks through the process of setting up a PostgreSQL database on Railway to work with our Kite Trading application.

## Why PostgreSQL?

We're moving from in-memory storage to PostgreSQL to fix several issues:
- Persistent authentication tokens across application restarts
- User settings storage
- Trading history and alerts for better analytics

## Setting Up PostgreSQL on Railway

### 1. Log in to your Railway account

- Go to [Railway.app](https://railway.app/) and log in to your account
- Navigate to your Kite Trading project

### 2. Add a PostgreSQL database service

1. Click on "New Service" within your project
2. Select "Database" from the options
3. Choose "PostgreSQL" as your database type
4. Click "Add" to create the PostgreSQL instance
5. Wait for the database to provision (usually takes under a minute)

### 3. Link the database to your app

1. Go to your PostgreSQL service dashboard
2. Click on "Connect" in the top right
3. Under "Environment Variables", you'll see `DATABASE_URL` 
4. Click "Add to Project" to add this connection string to your application

### 4. Configure the app to use PostgreSQL

No further configuration is needed as our application is already configured to use the `DATABASE_URL` environment variable. The system will:

1. Initialize database tables on first startup
2. Store authentication tokens with 24-hour expiration
3. Persist settings for trading parameters

## Deployment and Verification

### Deploying with the database

1. Push the updated code to your repository
2. Railway will automatically rebuild and deploy the application
3. During deployment, the `railway_setup.py` script will create the required database tables

### Verifying the Setup

1. After deployment, navigate to your app URL
2. Go to the authentication page and log in with Zerodha
3. After successful login, the user information and token should be stored in the database
4. The token should now persist for 24 hours and survive application restarts

## Troubleshooting

### If tables aren't created

Manually trigger the database creation by SSH into your Railway instance:
```bash
railway login
railway connect
python railway_setup.py
```

### Database connection issues

Check the logs for connection errors:
```bash
railway logs
```

Common issues include:
- Incorrect DATABASE_URL format
- Network connectivity problems
- Database service not fully provisioned

## Database Schema

Our application uses the following tables:

1. `users` - Stores user profile information
2. `auth_tokens` - Stores authentication tokens with expiration timestamps
3. `settings` - Stores application settings

## Data Persistence

- Zerodha tokens are stored in the database with a 24-hour expiration
- Application settings are saved in the database for persistence
- The system automatically checks for token validity before making API calls 