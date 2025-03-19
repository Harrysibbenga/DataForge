"""
app/db/models.py - Database models for DataForge
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Float, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timedelta


from app.db.config import Base

def generate_uuid():
    """Generate a UUID string"""
    return str(uuid.uuid4())

class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    company = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime, nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    conversions = relationship("Conversion", back_populates="user", cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user", cascade="all, delete-orphan")

class Subscription(Base):
    """User subscription model"""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Plan details
    plan = Column(String, default="free", nullable=False)  # free, basic, pro, enterprise
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Billing period
    start_date = Column(DateTime, default=func.now())
    end_date = Column(DateTime, default=lambda: datetime.now() + timedelta(days=30))
    
    # Usage limits
    conversion_count = Column(Integer, default=0)
    conversion_limit = Column(Integer, default=5)  # Default for free tier
    file_size_limit_mb = Column(Integer, default=5)  # In megabytes
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscription")

class ApiKey(Base):
    """API key model"""
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_used = Column(DateTime, nullable=True)
    permissions = Column(JSON, default={"convert": True, "read_stats": False})
    
    # Relationships
    user = relationship("User", back_populates="api_keys")

class Conversion(Base):
    """Data conversion record"""
    __tablename__ = "conversions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Conversion details
    file_name = Column(String, nullable=False)
    from_format = Column(String, nullable=False)
    to_format = Column(String, nullable=False)
    file_size_kb = Column(Float, nullable=True)  # In kilobytes
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    source = Column(String, default="web")  # web or api
    ip_address = Column(String, nullable=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    
    # Status and processing time
    status = Column(String, default="success")  # success, error
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)  # In milliseconds
    
    # Transformations applied
    transformations = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="conversions")
    api_key = relationship("ApiKey", backref="conversions")

class LoginHistory(Base):
    """User login history"""
    __tablename__ = "login_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    login_time = Column(DateTime, default=func.now())
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    location = Column(String, nullable=True)
    device = Column(String, nullable=True)
    success = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="login_history")
    
    
class SubscriptionHistory(Base):
    """Subscription history model to track changes"""
    __tablename__ = "subscription_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(String, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_subscription_id = Column(String, nullable=True, index=True)
    plan = Column(String, nullable=False)
    previous_plan = Column(String, nullable=True)
    action = Column(String, nullable=False)  # created, updated, cancelled, etc.
    action_date = Column(DateTime, default=func.now())
    status = Column(String, nullable=False)
    meta_data = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", backref="subscription_history")
    subscription = relationship("Subscription", backref="history")
