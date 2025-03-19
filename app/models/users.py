"""
app/models/users.py - Updated user models for enhanced authentication
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import re

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password strength"""
        # At least 8 characters, one uppercase, one lowercase, one number
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    remember_me: bool = False

class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    email: EmailStr

class PasswordReset(BaseModel):
    """Schema for password reset"""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def password_strength(cls, v):
        """Validate password strength"""
        # At least 8 characters, one uppercase, one lowercase, one number
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class UserSubscription(BaseModel):
    """Schema for user subscription details"""
    plan: str = "free"  # free, basic, pro, enterprise
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    conversion_count: int = 0
    conversion_limit: int = 5  # Default for free tier
    
    def is_limit_reached(self) -> bool:
        """Check if user has reached their conversion limit"""
        if self.plan == "enterprise":
            return False  # Unlimited
        return self.conversion_count >= self.conversion_limit
    
    def increment_count(self) -> int:
        """Increment the conversion count and return new value"""
        self.conversion_count += 1
        return self.conversion_count

class User(BaseModel):
    """Full user model with all details"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    full_name: str
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    subscription: UserSubscription = Field(default_factory=UserSubscription)
    api_keys: List[Dict[str, Any]] = []

class UserDB(User):
    """User model for database operations"""
    class Config:
        orm_mode = True

class UserResponse(BaseModel):
    """User model for API responses (without sensitive data)"""
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    subscription: UserSubscription
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    """Schema for authentication tokens"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Schema for decoded token data"""
    email: Optional[str] = None
    id: Optional[str] = None