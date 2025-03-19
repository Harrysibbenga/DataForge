"""
app/api/auth_routes.py - Authentication routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any, List

from app.models.users import (
    User, UserCreate, UserResponse, Token,
    UserSubscription
)
from app.auth.handlers import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_active_user, generate_api_key, mock_users_db
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate) -> User:
    """Register a new user"""
    # Check if user already exists
    if user_data.email in mock_users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        subscription=UserSubscription()  # Default free plan
    )
    
    # In a real application, you would save the user to a database
    mock_users_db[user_data.email] = user.dict()
    
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:
    """Authenticate user and return access token"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    user.last_login = datetime.now()
    mock_users_db[user.email] = user.dict()
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Get current user profile"""
    return current_user

@router.post("/api-keys", response_model=Dict[str, Any])
async def create_api_key(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Create a new API key for the current user"""
    # Generate a new API key
    api_key = generate_api_key()
    
    # Add to user's API keys
    user = mock_users_db[current_user.email]
    user_obj = User(**user)
    
    new_key = {
        "key": api_key,
        "name": f"API Key {len(user_obj.api_keys) + 1}",
        "created_at": datetime.now(),
        "is_active": True
    }
    
    user_obj.api_keys.append(new_key)
    mock_users_db[current_user.email] = user_obj.dict()
    
    return {
        "api_key": api_key,
        "created_at": new_key["created_at"]
    }

@router.get("/api-keys", response_model=List[Dict[str, Any]])
async def list_api_keys(current_user: User = Depends(get_current_active_user)) -> List[Dict[str, Any]]:
    """List all API keys for the current user"""
    # In a real application, you would not return the actual API keys,
    # just metadata about them
    sanitized_keys = []
    for key in current_user.api_keys:
        key_data = key.copy()
        # Mask the actual key
        key_data["key"] = f"{key['key'][:8]}...{key['key'][-4:]}"
        sanitized_keys.append(key_data)
    
    return sanitized_keys

@router.delete("/api-keys/{key_id}", response_model=Dict[str, Any])
async def revoke_api_key(key_id: str, current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Revoke an API key"""
    # In a real application, you would mark the API key as inactive in your database
    return {
        "status": "success",
        "message": "API key revoked successfully"
    }
