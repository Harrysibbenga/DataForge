"""
Updated app/api/routes.py with login, register, and API docs routes
"""

from fastapi import FastAPI, Depends, HTTPException, Request, File, Form, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import logging

from app.core.converter import DataConverter
from app.core.transformations import (
    remove_empty_rows,
    remove_empty_columns,
    standardize_column_names,
    trim_whitespace,
    deduplicate_rows
)

# Import the router modules
from app.api.auth_routes import router as auth_router
from app.api.payment_routes import router as payment_router
from app.api.dashboard_routes import router as dashboard_router

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Include auth, payment, and dashboard routers
app.include_router(auth_router)
app.include_router(payment_router)
app.include_router(dashboard_router)

# Create templates instance - note the path is relative to the project root
templates = Jinja2Templates(directory="app/templates")

# Mount static files - note the path is relative to the project root
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize converter
converter = DataConverter()

# Main HTML page routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Render the pricing page"""
    return templates.TemplateResponse("pricing.html", {"request": request})

@app.get("/payment/thank-you", response_class=HTMLResponse)
async def thank_you_page(request: Request):
    """Render the thank you page"""
    return templates.TemplateResponse("thank_you.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Render the registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/api-docs", response_class=HTMLResponse)
async def api_docs_page(request: Request):
    """Render the API documentation page"""
    return templates.TemplateResponse("api_docs.html", {"request": request})

# API routes
@app.post("/api/convert")
async def convert_data(
    file: UploadFile = File(...),
    to_format: str = Form(...),
    remove_empty_rows_flag: bool = Form(False),
    remove_empty_cols_flag: bool = Form(False),
    standardize_names_flag: bool = Form(False),
    trim_whitespace_flag: bool = Form(False),
    deduplicate_flag: bool = Form(False)
):
    """
    Convert uploaded file to specified format with optional transformations
    """
    try:
        # Read the uploaded file
        content = await file.read()
        
        # Detect source format
        from_format = converter.detect_format(file.filename)
        
        # Build transformation pipeline
        transformations = []
        if remove_empty_rows_flag:
            transformations.append(remove_empty_rows)
        if remove_empty_cols_flag:
            transformations.append(remove_empty_columns)
        if standardize_names_flag:
            transformations.append(standardize_column_names)
        if trim_whitespace_flag:
            transformations.append(trim_whitespace)
        if deduplicate_flag:
            transformations.append(deduplicate_rows)
        
        # Convert the data
        result = converter.convert(content, from_format, to_format, transformations)
        
        # Generate output filename
        output_filename = f"{os.path.splitext(file.filename)[0]}.{to_format}"
        
        # Create response
        response = StreamingResponse(
            io.BytesIO(result.encode() if isinstance(result, str) else result),
            media_type="application/octet-stream",
        )
        response.headers["Content-Disposition"] = f"attachment; filename={output_filename}"
        
        return response
    
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/formats")
async def get_formats():
    """Get list of supported formats"""
    return {
        "formats": list(converter.SUPPORTED_FORMATS.keys())
    }

# Redirect /api/docs to FastAPI's auto-generated docs
@app.get("/api/docs")
async def api_swagger_docs():
    """Redirect to FastAPI's auto-generated docs"""
    return RedirectResponse(url="/docs")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render the dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Add settings route (dashboard will redirect here)
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Redirect to dashboard with settings tab active"""
    return RedirectResponse(url="/dashboard#profile")