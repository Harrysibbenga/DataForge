"""
app/api/auth_routes.py - Complete authentication routes implementation
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import re
import secrets
import json

from app.models.users import (
    User, UserCreate, UserResponse, Token, PasswordResetRequest, PasswordReset, UserLogin
)
from app.auth.handlers import (
    get_password_hash, create_access_token, 
    get_current_active_user, generate_api_key,
    verify_password, get_current_user
)
from app.auth.email_utils import (
    generate_verification_token, verify_email_token,
    generate_password_reset_token, verify_password_reset_token,
    send_verification_email, send_password_reset_email,
    send_welcome_email
)
from app.db.config import get_db
import app.db.crud as crud

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Define the OAuth2 password bearer token for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Register a new user with email verification"""
    # Check if user already exists
    db_user = crud.get_user_by_email(db, user_data.email)
    if db_user:
        if db_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            # Resend verification email for unverified users
            verification_token = generate_verification_token(db_user.email)
            base_url = str(request.base_url).rstrip('/')
            
            # Send verification email
            email_sent = send_verification_email(
                email=db_user.email,
                token=verification_token,
                base_url=base_url
            )
            
            if not email_sent:
                logger.warning(f"Failed to send verification email to {db_user.email}")
            
            return {
                "status": "verification_needed",
                "message": "This email is already registered but not verified. A new verification email has been sent."
            }
    
    # Create new user (unverified)
    user = crud.create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        is_verified=False
    )
    
    # Record client information
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    # Create login record
    crud.record_login(
        db=db,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True
    )
    
    # Generate verification token
    verification_token = generate_verification_token(user.email)
    base_url = str(request.base_url).rstrip('/')
    
    # Send verification email
    email_sent = send_verification_email(
        email=user.email,
        token=verification_token,
        base_url=base_url
    )
    
    if not email_sent:
        logger.warning(f"Failed to send verification email to {user.email}")
    
    # Return user data with verification information
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name
        },
        "status": "verification_needed",
        "message": "Registration successful. Please check your email to verify your account."
    }

@router.get("/verify-email", response_model=Dict[str, Any])
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Verify user's email address with token"""
    try:
        email = verify_email_token(token)
        
        # Get user by email
        user = crud.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user is already verified
        if user.is_verified:
            return {
                "status": "already_verified",
                "message": "Your email address has already been verified."
            }
        
        # Update user as verified
        user = crud.update_user(
            db=db,
            user_id=user.id,
            is_verified=True
        )
        
        # Send welcome email
        send_welcome_email(user.email, user.full_name)
        
        # Create access token
        access_token_expires = timedelta(minutes=60 * 24)  # 24 hours
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        return {
            "status": "success",
            "message": "Email verification successful. Your account is now active.",
            "access_token": access_token,
            "token_type": "bearer",
            "email": user.email
        }
        
    except HTTPException as e:
        # Re-raise HTTPExceptions for specific error handling
        raise
    except Exception as e:
        logger.error(f"Error verifying email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Authenticate user and return access token"""
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Record failed login attempt if email exists
        db_user = crud.get_user_by_email(db, form_data.username)
        if db_user:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")
            
            crud.record_login(
                db=db,
                user_id=db_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is verified
    if not user.is_verified:
        # Generate new verification token
        verification_token = generate_verification_token(user.email)
        base_url = str(request.base_url).rstrip('/')
        
        # Resend verification email
        send_verification_email(
            email=user.email,
            token=verification_token,
            base_url=base_url
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. A new verification email has been sent."
        )
    
    # Record successful login
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    crud.record_login(
        db=db,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True
    )
    
    # Create access token
    access_token_expires = timedelta(minutes=60 * 24)  # 24 hours
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Alternative login endpoint with remember me option"""
    user = crud.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        # Record failed login attempt if email exists
        db_user = crud.get_user_by_email(db, login_data.email)
        if db_user:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")
            
            crud.record_login(
                db=db,
                user_id=db_user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # Check if user is verified
    if not user.is_verified:
        # Generate new verification token
        verification_token = generate_verification_token(user.email)
        base_url = str(request.base_url).rstrip('/')
        
        # Resend verification email
        send_verification_email(
            email=user.email,
            token=verification_token,
            base_url=base_url
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. A new verification email has been sent."
        )
    
    # Record successful login
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    crud.record_login(
        db=db,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True
    )
    
    # Create access token - longer expiration if remember_me is set
    if login_data.remember_me:
        access_token_expires = timedelta(days=30)  # 30 days for "remember me"
    else:
        access_token_expires = timedelta(hours=24)  # 24 hours by default
        
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "remember_me": login_data.remember_me
    }

@router.post("/forgot-password", response_model=Dict[str, Any])
async def forgot_password(
    email_data: Dict[str, str] = Body(...),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Request password reset via email"""
    email = email_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Check if user exists
    user = crud.get_user_by_email(db, email)
    
    # For security, don't reveal whether the user exists
    # Always return success message
    if not user:
        logger.info(f"Password reset requested for non-existent email: {email}")
        return {
            "status": "success",
            "message": "If your email is registered, you will receive password reset instructions."
        }
    
    # Generate password reset token
    reset_token = generate_password_reset_token(email)
    base_url = str(request.base_url).rstrip('/')
    
    # Send password reset email
    email_sent = send_password_reset_email(
        email=email,
        token=reset_token,
        base_url=base_url
    )
    
    if not email_sent:
        logger.warning(f"Failed to send password reset email to {email}")
    
    return {
        "status": "success",
        "message": "If your email is registered, you will receive password reset instructions."
    }

@router.post("/reset-password", response_model=Dict[str, Any])
async def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Reset user password using reset token"""
    try:
        # Verify token and get email
        email = verify_password_reset_token(reset_data.token)
        
        # Get user by email
        user = crud.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        hashed_password = get_password_hash(reset_data.new_password)
        crud.update_user(
            db=db,
            user_id=user.id,
            hashed_password=hashed_password
        )
        
        return {
            "status": "success",
            "message": "Password reset successful. You can now log in with your new password."
        }
        
    except HTTPException as e:
        # Re-raise HTTPExceptions for specific error handling
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

@router.get("/resend-verification", response_model=Dict[str, Any])
async def resend_verification(
    email: str,
    request: Request,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Resend verification email to user"""
    # Check if email is provided
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )
    
    # Get user by email
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is already verified
    if user.is_verified:
        return {
            "status": "already_verified",
            "message": "Your email address has already been verified."
        }
    
    # Generate verification token
    verification_token = generate_verification_token(user.email)
    base_url = str(request.base_url).rstrip('/')
    
    # Send verification email
    email_sent = send_verification_email(
        email=user.email,
        token=verification_token,
        base_url=base_url
    )
    
    if not email_sent:
        logger.warning(f"Failed to send verification email to {user.email}")
        return {
            "status": "error",
            "message": "Failed to send verification email. Please try again later."
        }
    
    return {
        "status": "success",
        "message": "Verification email sent. Please check your inbox."
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user profile"""
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> User:
    """Update user profile information"""
    # Validate and extract fields
    allowed_fields = ["full_name", "company"]
    update_data = {k: v for k, v in profile_data.items() if k in allowed_fields}
    
    # Update user
    updated_user = crud.update_user(
        db=db,
        user_id=current_user.id,
        **update_data
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return updated_user

@router.post("/logout", response_model=Dict[str, Any])
async def logout(
    request: Request = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Log out the current user
    
    Note: This is a server-side endpoint for logging actions.
    Token invalidation happens client-side by removing the token.
    """
    # Record logout action
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    # You could maintain a blacklist of invalidated tokens
    # or just log the logout event
    logger.info(f"User {current_user.email} logged out from {ip_address}")
    
    return {
        "status": "success",
        "message": "Logged out successfully"
    }

@router.post("/api-keys", response_model=Dict[str, Any])
async def create_api_key(
    name: str,
    read_stats: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new API key for the current user"""
    # Check if user has reached their API key limit for their plan
    api_key_limits = {
        "free": 1,
        "basic": 3,
        "pro": 5,
        "enterprise": 10
    }
    
    # Get user's subscription
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no active subscription"
        )
    
    # Get active API keys
    active_keys = crud.get_user_api_keys(db, current_user.id)
    
    # Check against limit
    plan = subscription.plan
    key_limit = api_key_limits.get(plan, 1)
    
    if len(active_keys) >= key_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have reached the maximum number of API keys ({key_limit}) for your plan"
        )
    
    # Create permissions
    permissions = {
        "convert": True,
        "read_stats": read_stats
    }
    
    # Create API key
    api_key = crud.create_api_key(
        db=db,
        user_id=current_user.id,
        name=name,
        permissions=permissions
    )
    
    return {
        "id": api_key.id,
        "key": api_key.key,
        "name": api_key.name,
        "created_at": api_key.created_at
    }

@router.get("/api-keys", response_model=List[Dict[str, Any]])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all API keys for the current user"""
    # Get active API keys
    api_keys = crud.get_user_api_keys(db, current_user.id)
    
    # Mask the actual keys for security
    sanitized_keys = []
    for key in api_keys:
        # Mask the key except first and last 4 chars
        full_key = key.key
        masked_key = f"{full_key[:8]}...{full_key[-4:]}" if len(full_key) > 12 else full_key
        
        sanitized_keys.append({
            "id": key.id,
            "name": key.name,
            "key": masked_key,
            "created_at": key.created_at,
            "last_used": key.last_used
        })
    
    return sanitized_keys

@router.delete("/api-keys/{key_id}", response_model=Dict[str, Any])
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Revoke an API key"""
    # Check if the key belongs to the user
    success = crud.revoke_api_key(db, key_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return {
        "status": "success",
        "message": "API key revoked successfully"
    }

@router.post("/change-password", response_model=Dict[str, str])
async def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Change user password"""
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Validate new password
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    if not re.search(r'[A-Z]', new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter"
        )
        
    if not re.search(r'[a-z]', new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter"
        )
        
    if not re.search(r'[0-9]', new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number"
        )
    
    # Update password
    hashed_password = get_password_hash(new_password)
    crud.update_user(
        db=db,
        user_id=current_user.id,
        hashed_password=hashed_password
    )
    
    # Log password change
    logger.info(f"Password changed for user {current_user.email}")
    
    return {"message": "Password updated successfully"}

@router.get("/check-auth", response_model=Dict[str, Any])
async def check_auth(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Check if the user is authenticated and the token is valid"""
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "is_verified": current_user.is_verified
        }
    }

@router.get("/login-history", response_model=List[Dict[str, Any]])
async def get_login_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, gt=0, le=100)
) -> List[Dict[str, Any]]:
    """Get user's login history"""
    # Get login history records
    history = crud.get_user_login_history(db, current_user.id, limit)
    
    # Format for response
    result = []
    for entry in history:
        result.append({
            "id": entry.id,
            "login_time": entry.login_time,
            "ip_address": entry.ip_address,
            "user_agent": entry.user_agent,
            "device": entry.device,
            "location": entry.location,
            "success": entry.success
        })
    
    return result