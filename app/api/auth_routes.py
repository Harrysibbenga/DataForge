"""
app/api/auth_routes.py - Authentication routes with database integration
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.models.users import (
    User, UserCreate, UserResponse, Token
)
from app.auth.handlers import (
    get_password_hash, create_access_token, 
    get_current_active_user, generate_api_key,
    verify_password
)
from app.db.config import get_db
import app.db.crud as crud
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Register a new user"""
    # Check if user already exists
    db_user = crud.get_user_by_email(db, user_data.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = crud.create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
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
    
    return user

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

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user profile"""
    return current_user

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
    current_password: str,
    new_password: str,
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
    
    # Update password
    hashed_password = get_password_hash(new_password)
    crud.update_user(
        db=db,
        user_id=current_user.id,
        hashed_password=hashed_password
    )
    
    return {"message": "Password updated successfully"}