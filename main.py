"""
DataForge - Data Conversion Tool
Main application entry point
"""
import uvicorn
from app.db import init_db

# Initialize database on startup
init_db()

# Import app after initializing database to avoid circular imports
from app.api.routes import app

if __name__ == "__main__":
    # Run the application
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)