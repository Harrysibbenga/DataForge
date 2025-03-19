"""
app/db/__init__.py - Database initialization
"""
from app.db.config import Base, engine

def init_db():
    """Initialize the database by creating all tables"""
    # Import all models here to ensure they're registered with Base
    from app.db.models import User, Subscription, ApiKey, Conversion, LoginHistory
    
    # Create tables
    Base.metadata.create_all(bind=engine)
