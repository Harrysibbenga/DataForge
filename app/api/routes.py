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
import datetime

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

from sqlalchemy.orm import Session
from app.db.config import get_db
import app.db.crud as crud
from app.auth.handlers import get_user_from_request

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
"""
Updated conversion endpoint for DataForge
"""
@app.post("/api/convert")
async def convert_data(
    request: Request,
    file: UploadFile = File(...),
    to_format: str = Form(...),
    remove_empty_rows_flag: bool = Form(False),
    remove_empty_cols_flag: bool = Form(False),
    standardize_names_flag: bool = Form(False),
    trim_whitespace_flag: bool = Form(False),
    deduplicate_flag: bool = Form(False),
    db: Session = Depends(get_db)
):
    """
    Convert uploaded file to specified format with optional transformations
    
    This endpoint supports both authenticated web users and API keys.
    """
    try:
        start_time = datetime.now()
        
        # Get user from request (either from JWT token or API key)
        user = await get_user_from_request(request, db=db)
        
        # If no valid user found, return unauthorized
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer or API Key"},
            )
        
        # Get API key if present
        api_key = request.headers.get("X-API-Key")
        api_key_id = None
        
        if api_key:
            db_api_key = crud.get_api_key_by_key(db, api_key)
            if db_api_key:
                api_key_id = db_api_key.id
        
        # Check if user has reached their conversion limit
        is_limit_reached, current_count, limit = crud.check_conversion_limit(db, user.id)
        
        if is_limit_reached:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Conversion limit reached ({current_count}/{limit}). Please upgrade your plan."
            )
        
        # Get user's subscription for file size limit
        subscription = crud.get_user_subscription(db, user.id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no active subscription"
            )
        
        # Check file size limit
        file_size_bytes = 0
        content = await file.read()
        file_size_bytes = len(content)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        if file_size_mb > subscription.file_size_limit_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds the limit for your plan ({file_size_mb:.2f}MB > {subscription.file_size_limit_mb}MB)"
            )
        
        # Seek back to the start of the file
        file.file.seek(0)
        
        # Detect source format
        try:
            from_format = converter.detect_format(file.filename)
        except ValueError as e:
            # Record failed conversion
            crud.record_conversion(
                db=db,
                user_id=user.id,
                file_name=file.filename,
                from_format="unknown",
                to_format=to_format,
                file_size_kb=file_size_bytes / 1024,
                source="api" if api_key else "web",
                ip_address=request.client.host if request.client else None,
                api_key_id=api_key_id,
                status="error",
                error_message=str(e)
            )
            raise HTTPException(status_code=400, detail=str(e))
        
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
        
        # Compile list of applied transformations
        applied_transformations = {
            "remove_empty_rows": remove_empty_rows_flag,
            "remove_empty_columns": remove_empty_cols_flag,
            "standardize_names": standardize_names_flag,
            "trim_whitespace": trim_whitespace_flag,
            "deduplicate": deduplicate_flag
        }
        
        # Convert the data
        try:
            result = converter.convert(content, from_format, to_format, transformations)
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Record successful conversion
            crud.record_conversion(
                db=db,
                user_id=user.id,
                file_name=file.filename,
                from_format=from_format,
                to_format=to_format,
                file_size_kb=file_size_bytes / 1024,
                source="api" if api_key else "web",
                ip_address=request.client.host if request.client else None,
                api_key_id=api_key_id,
                status="success",
                processing_time_ms=processing_time_ms,
                transformations=applied_transformations
            )
            
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
            # Record failed conversion
            end_time = datetime.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            crud.record_conversion(
                db=db,
                user_id=user.id,
                file_name=file.filename,
                from_format=from_format,
                to_format=to_format,
                file_size_kb=file_size_bytes / 1024,
                source="api" if api_key else "web",
                ip_address=request.client.host if request.client else None,
                api_key_id=api_key_id,
                status="error",
                error_message=str(e),
                processing_time_ms=processing_time_ms,
                transformations=applied_transformations
            )
            
            raise HTTPException(status_code=400, detail=str(e))
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Log the error
        logger.error(f"Error during conversion: {str(e)}")
        
        # Return error response
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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

# Email verification route
@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request):
    """Render the email verification page"""
    return templates.TemplateResponse("verify-email.html", {"request": request})

# Resend verification email route
@app.get("/resend-verification", response_class=HTMLResponse)
async def resend_verification_page(request: Request):
    """Render the resend verification page"""
    return templates.TemplateResponse("resend-verification.html", {"request": request})

# Forgot password route
@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Render the forgot password page"""
    return templates.TemplateResponse("forgot-password.html", {"request": request})

# Reset password route
@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    """Render the reset password page"""
    return templates.TemplateResponse("reset-password.html", {"request": request})