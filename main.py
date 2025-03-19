"""
DataForge - Data Conversion Tool
Main application entry point with scheduler integration
"""
import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import atexit

from app.db import init_db
from app.scheduler import start_scheduler, shutdown_scheduler
from app.api.routes import app as api_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database on startup
init_db()

# Create the main FastAPI application
app = FastAPI(
    title="DataForge",
    description="A powerful data conversion tool",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the API app
app.mount("/", api_app)

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    # Start the scheduler
    start_scheduler()
    logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    # Shutdown the scheduler
    shutdown_scheduler()
    logger.info("Application shutdown successfully")

# Register shutdown handler for non-graceful terminations
atexit.register(shutdown_scheduler)

if __name__ == "__main__":
    # Run the application
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)