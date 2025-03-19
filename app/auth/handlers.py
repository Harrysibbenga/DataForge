"""
app/auth/handlers.py - Authentication and authorization handlers
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os
import secrets
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.users import TokenData
from app.db.config import get_db
from app.db.models import User, ApiKey
import app.db.crud as crud

# Security configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token verification
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from the token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    user = crud.get_user_by_email(db, token_data.email)
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"df_{secrets.token_urlsafe(32)}"

async def get_api_key_user(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Validate API key and return the associated user"""
    if not api_key:
        return None
    
    db_api_key = crud.get_api_key_by_key(db, api_key)
    if not db_api_key:
        return None
    
    # Update last used timestamp
    db_api_key.last_used = datetime.now()
    db.commit()
    
    return crud.get_user(db, db_api_key.user_id)

async def get_user_from_request(
    request: Request,
    token: str = Depends(oauth2_scheme),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get user from either JWT token or API key
    
    Tries to get user from JWT token first, then falls back to API key.
    Returns None if neither are valid.
    """
    user = None
    
    # Try JWT token first
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                user = crud.get_user_by_email(db, email)
        except (JWTError, ValidationError):
            pass
    
    # Fall back to API key
    if not user and api_key:
        db_api_key = crud.get_api_key_by_key(db, api_key)
        if db_api_key:
            user = crud.get_user(db, db_api_key.user_id)
            
            # Update last used timestamp
            db_api_key.last_used = datetime.now()
            db.commit()
    
    # Record client info for analytics (if user found)
    if user:
        # Extract client info from request
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        
        # In a real app, you might use a geo-IP service to determine location
        location = None
        
        # Parse device from user agent (simplified)
        device = None
        if user_agent:
            if "Windows" in user_agent:
                device = "Windows"
            elif "Mac" in user_agent:
                device = "Mac"
            elif "Android" in user_agent:
                device = "Android"
            elif "iOS" in user_agent or "iPhone" in user_agent or "iPad" in user_agent:
                device = "iOS"
            elif "Linux" in user_agent:
                device = "Linux"
    
    return user

# Add these additional functions to your auth/handlers.py file

async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current user if authenticated, without requiring authentication
    
    This is useful for routes that work with or without authentication.
    Returns None if no valid token is provided.
    """
    if not token:
        return None
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        token_data = TokenData(email=email)
    except (JWTError, ValidationError):
        return None
    
    user = crud.get_user_by_email(db, token_data.email)
    if not user:
        return None
    
    return user

async def validate_api_key_permissions(
    required_permissions: List[str],
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> bool:
    """
    Validate that an API key has the required permissions
    
    Args:
        required_permissions: List of permission strings required (e.g., ["convert", "read_stats"])
        api_key: API key from header
        db: Database session
        
    Returns:
        True if the API key has all required permissions, False otherwise
    """
    if not api_key:
        return False
    
    # Get API key from database
    db_api_key = crud.get_api_key_by_key(db, api_key)
    if not db_api_key:
        return False
    
    # Get permissions
    permissions = db_api_key.permissions or {}
    
    # Check if all required permissions are present and set to True
    for permission in required_permissions:
        if not permissions.get(permission, False):
            return False
    
    # Update last used timestamp
    db_api_key.last_used = datetime.now()
    db.commit()
    
    return True

def get_token_from_cookie(request: Request) -> Optional[str]:
    """
    Extract JWT token from cookies for alternative authentication method
    
    This allows "remember me" functionality using cookies
    """
    token = request.cookies.get("access_token")
    return token

def get_ip_info(ip_address: str) -> Dict[str, Any]:
    """
    Get information about an IP address using a geolocation service
    
    In a production environment, you would integrate with a real
    geolocation service. This is a placeholder implementation.
    """
    # Placeholder - in a real app, you'd call a geolocation API
    return {
        "country": "Unknown",
        "city": "Unknown",
        "region": "Unknown",
        "location": "Unknown"
    }