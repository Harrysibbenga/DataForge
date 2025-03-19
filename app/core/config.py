"""
app/core/config.py - Application configuration settings
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings, PostgresDsn, validator
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    APP_NAME: str = "DataForge"
    APP_ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # Database settings
    DATABASE_URL: PostgresDsn = "postgresql://dataforge_user:your_secure_password@localhost/dataforge"
    
    # JWT settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Stripe settings
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_BASIC_PRICE_ID: Optional[str] = None
    STRIPE_PRO_PRICE_ID: Optional[str] = None
    STRIPE_ENTERPRISE_PRICE_ID: Optional[str] = None
    
    # CORS settings
    CORS_ORIGINS: list = ["*"]
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]
    
    # Plan limits
    PLAN_LIMITS: Dict[str, Dict[str, int]] = {
        "free": {
            "conversion_limit": 5,
            "file_size_limit_mb": 5,
            "api_keys_limit": 1,
        },
        "basic": {
            "conversion_limit": 100,
            "file_size_limit_mb": 50,
            "api_keys_limit": 3,
        },
        "pro": {
            "conversion_limit": 500,
            "file_size_limit_mb": 100,
            "api_keys_limit": 5,
        },
        "enterprise": {
            "conversion_limit": 9999,  # Effectively unlimited
            "file_size_limit_mb": 500,
            "api_keys_limit": 10,
        },
    }
    
    # Validators
    @validator("DATABASE_URL", pre=True)
    def validate_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        """Validate database connection string"""
        # If DATABASE_URL is provided in the environment, use it
        # Otherwise, construct it from individual components (for use with Docker)
        if os.getenv("POSTGRES_USER") and not v:
            return PostgresDsn.build(
                scheme="postgresql",
                user=os.getenv("POSTGRES_USER", ""),
                password=os.getenv("POSTGRES_PASSWORD", ""),
                host=os.getenv("POSTGRES_HOST", "db"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                path=f"/{os.getenv('POSTGRES_DB', '')}",
            )
        return v
    
    class Config:
        """Pydantic config"""
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings, cached for efficiency
    
    When using this function, settings are loaded once and reused.
    """
    return Settings()
