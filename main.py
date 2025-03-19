"""
DataForge - Data Conversion Tool
Main application entry point
"""
import uvicorn

if __name__ == "__main__":
    # Import app here to avoid potential circular imports
    from app.api.routes import app
    
    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8000)