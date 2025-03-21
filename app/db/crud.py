"""
app/db/crud.py - CRUD operations for database models
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Dict, List, Optional, Any, Tuple
import uuid
from datetime import datetime, timedelta
from app.db.models import User, Subscription, ApiKey, Conversion, LoginHistory, SubscriptionHistory
from app.auth.handlers import get_password_hash, verify_password, generate_api_key

# User operations
def get_user(db: Session, user_id: str) -> Optional[User]:
    """Get a user by ID"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email"""
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, email: str, password: str, full_name: str, is_verified: bool = False) -> User:
    """
    Create a new user
    
    Args:
        db: Database session
        email: User's email
        password: User's password (will be hashed)
        full_name: User's full name
        is_verified: Whether the user's email is verified
        
    Returns:
        Newly created user
    """
    hashed_password = get_password_hash(password)
    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_verified=is_verified  # Add this parameter
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default subscription (free tier)
    create_subscription(db, user.id)
    
    return user

def update_user(db: Session, user_id: str, **kwargs) -> Optional[User]:
    """
    Update user fields
    
    Args:
        db: Database session
        user_id: ID of user to update
        **kwargs: Fields to update
        
    Returns:
        Updated user or None if not found
    """
    user = get_user(db, user_id)
    if not user:
        return None
        
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: str) -> bool:
    """Delete a user"""
    user = get_user(db, user_id)
    if not user:
        return False
        
    db.delete(user)
    db.commit()
    return True

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user with email and password
    
    Args:
        db: Database session
        email: User's email
        password: User's password (plaintext)
        
    Returns:
        User if authentication is successful, None otherwise
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def record_login(
    db: Session, 
    user_id: str, 
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    location: Optional[str] = None,
    device: Optional[str] = None,
    success: bool = True
) -> LoginHistory:
    """Record a login attempt"""
    login_record = LoginHistory(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        location=location,
        device=device,
        success=success
    )
    db.add(login_record)
    db.commit()
    db.refresh(login_record)
    
    # Update user's last_login if successful
    if success:
        user = get_user(db, user_id)
        if user:
            user.last_login = func.now()
            db.commit()
    
    return login_record

# Subscription operations
def get_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
    """Get a subscription by ID"""
    return db.query(Subscription).filter(Subscription.id == subscription_id).first()

def get_user_subscription(db: Session, user_id: str) -> Optional[Subscription]:
    """Get a user's subscription"""
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()

def create_subscription(db: Session, user_id: str, plan: str = "free") -> Subscription:
    """Create a subscription for a user"""
    # Set limits based on plan
    limits = {
        "free": {"conversion_limit": 5, "file_size_limit_mb": 5},
        "basic": {"conversion_limit": 100, "file_size_limit_mb": 50},
        "pro": {"conversion_limit": 500, "file_size_limit_mb": 100},
        "enterprise": {"conversion_limit": 9999, "file_size_limit_mb": 500},
    }
    
    subscription = Subscription(
        user_id=user_id,
        plan=plan,
        conversion_limit=limits[plan]["conversion_limit"],
        file_size_limit_mb=limits[plan]["file_size_limit_mb"]
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

def update_subscription(db: Session, user_id: str, **kwargs) -> Optional[Subscription]:
    """Update a user's subscription"""
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        return None
        
    for key, value in kwargs.items():
        if hasattr(subscription, key):
            setattr(subscription, key, value)
    
    db.commit()
    db.refresh(subscription)
    return subscription

def upgrade_subscription(db: Session, user_id: str, new_plan: str) -> Optional[Subscription]:
    """Upgrade a user's subscription to a new plan"""
    # Set limits based on plan
    limits = {
        "free": {"conversion_limit": 5, "file_size_limit_mb": 5},
        "basic": {"conversion_limit": 100, "file_size_limit_mb": 50},
        "pro": {"conversion_limit": 500, "file_size_limit_mb": 100},
        "enterprise": {"conversion_limit": 9999, "file_size_limit_mb": 500},
    }
    
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        return None
    
    subscription.plan = new_plan
    subscription.conversion_limit = limits[new_plan]["conversion_limit"]
    subscription.file_size_limit_mb = limits[new_plan]["file_size_limit_mb"]
    subscription.updated_at = func.now()
    
    db.commit()
    db.refresh(subscription)
    return subscription

def increment_conversion_count(db: Session, user_id: str) -> Tuple[int, int]:
    """
    Increment a user's conversion count
    
    Returns:
        Tuple of (new count, limit)
    """
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        return (0, 0)
    
    subscription.conversion_count += 1
    db.commit()
    
    return (subscription.conversion_count, subscription.conversion_limit)

def check_conversion_limit(db: Session, user_id: str) -> Tuple[bool, int, int]:
    """
    Check if a user has reached their conversion limit
    
    Returns:
        Tuple of (is_limit_reached, current_count, limit)
    """
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        return (True, 0, 0)
    
    # Enterprise users have unlimited conversions
    if subscription.plan == "enterprise":
        return (False, subscription.conversion_count, subscription.conversion_limit)
    
    is_limit_reached = subscription.conversion_count >= subscription.conversion_limit
    return (is_limit_reached, subscription.conversion_count, subscription.conversion_limit)

# API Key operations
def get_api_key(db: Session, key_id: str) -> Optional[ApiKey]:
    """Get an API key by ID"""
    return db.query(ApiKey).filter(ApiKey.id == key_id).first()

def get_api_key_by_key(db: Session, key: str) -> Optional[ApiKey]:
    """Get an API key by the key value"""
    return db.query(ApiKey).filter(ApiKey.key == key, ApiKey.is_active == True).first()

def get_user_api_keys(db: Session, user_id: str) -> List[ApiKey]:
    """Get all API keys for a user"""
    return db.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.is_active == True).all()

def create_api_key(db: Session, user_id: str, name: str, permissions: Dict = None) -> ApiKey:
    """Create a new API key for a user"""
    if permissions is None:
        permissions = {"convert": True, "read_stats": False}
    
    key = generate_api_key()
    api_key = ApiKey(
        user_id=user_id,
        key=key,
        name=name,
        permissions=permissions
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key

def revoke_api_key(db: Session, key_id: str, user_id: str) -> bool:
    """Revoke an API key"""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user_id).first()
    if not api_key:
        return False
    
    api_key.is_active = False
    db.commit()
    return True

def update_api_key_usage(db: Session, key_id: str) -> Optional[ApiKey]:
    """Update the last_used timestamp for an API key"""
    api_key = get_api_key(db, key_id)
    if not api_key:
        return None
    
    api_key.last_used = func.now()
    db.commit()
    db.refresh(api_key)
    return api_key

# Conversion operations
def record_conversion(
    db: Session,
    user_id: str,
    file_name: str,
    from_format: str,
    to_format: str,
    file_size_kb: Optional[float] = None,
    source: str = "web",
    ip_address: Optional[str] = None,
    api_key_id: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    processing_time_ms: Optional[int] = None,
    transformations: Optional[Dict] = None
) -> Conversion:
    """Record a data conversion"""
    conversion = Conversion(
        user_id=user_id,
        file_name=file_name,
        from_format=from_format,
        to_format=to_format,
        file_size_kb=file_size_kb,
        source=source,
        ip_address=ip_address,
        api_key_id=api_key_id,
        status=status,
        error_message=error_message,
        processing_time_ms=processing_time_ms,
        transformations=transformations
    )
    db.add(conversion)
    db.commit()
    db.refresh(conversion)
    
    # Increment conversion count if successful
    if status == "success":
        increment_conversion_count(db, user_id)
    
    # Update API key usage if used
    if api_key_id:
        update_api_key_usage(db, api_key_id)
    
    return conversion

def get_user_conversions(db: Session, user_id: str, limit: int = 100) -> List[Conversion]:
    """Get a user's conversion history"""
    return db.query(Conversion).filter(Conversion.user_id == user_id).order_by(desc(Conversion.created_at)).limit(limit).all()

def get_conversion_stats(db: Session, user_id: str) -> Dict[str, Any]:
    """Get statistics about a user's conversions"""
    # Get total successful conversions
    successful = db.query(func.count(Conversion.id)).filter(
        Conversion.user_id == user_id, 
        Conversion.status == "success"
    ).scalar()
    
    # Get total errors
    errors = db.query(func.count(Conversion.id)).filter(
        Conversion.user_id == user_id, 
        Conversion.status == "error"
    ).scalar()
    
    # Get format distribution
    format_pairs = db.query(
        Conversion.from_format, 
        Conversion.to_format, 
        func.count(Conversion.id).label("count")
    ).filter(
        Conversion.user_id == user_id,
        Conversion.status == "success"
    ).group_by(Conversion.from_format, Conversion.to_format).all()
    
    format_distribution = {}
    for from_format, to_format, count in format_pairs:
        pair = f"{from_format}_to_{to_format}"
        format_distribution[pair] = count
    
    # Get source distribution (web vs API)
    source_distribution = {}
    sources = db.query(
        Conversion.source, 
        func.count(Conversion.id).label("count")
    ).filter(
        Conversion.user_id == user_id
    ).group_by(Conversion.source).all()
    
    for source, count in sources:
        source_distribution[source] = count
    
    return {
        "total": successful + errors,
        "successful": successful,
        "errors": errors,
        "format_distribution": format_distribution,
        "source_distribution": source_distribution
    }


"""
Updates to app/db/crud.py for subscription history functionality
"""

# Add these new functions to your crud.py file

def record_subscription_history(
    db: Session,
    user_id: str,
    subscription_id: str,
    stripe_subscription_id: Optional[str],
    plan: str,
    previous_plan: Optional[str],
    action: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> SubscriptionHistory:
    """
    Record a subscription history entry
    
    Args:
        db: Database session
        user_id: User ID
        subscription_id: Subscription ID
        stripe_subscription_id: Stripe subscription ID (optional)
        plan: Current plan
        previous_plan: Previous plan (optional)
        action: Action type (created, updated, cancelled, etc.)
        status: Status of the subscription
        metadata: Additional metadata (optional)
        
    Returns:
        The created subscription history entry
    """
    history_entry = SubscriptionHistory(
        user_id=user_id,
        subscription_id=subscription_id,
        stripe_subscription_id=stripe_subscription_id,
        plan=plan,
        previous_plan=previous_plan,
        action=action,
        status=status,
        metadata=metadata or {}
    )
    
    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)
    
    return history_entry

def get_subscription_history(
    db: Session,
    user_id: str,
    limit: int = 10
) -> List[SubscriptionHistory]:
    """
    Get subscription history for a user
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of entries to return
        
    Returns:
        List of subscription history entries
    """
    return db.query(SubscriptionHistory)\
        .filter(SubscriptionHistory.user_id == user_id)\
        .order_by(SubscriptionHistory.action_date.desc())\
        .limit(limit)\
        .all()

def update_subscription_with_history(
    db: Session,
    user_id: str,
    action: str,
    updates: Dict[str, Any]
) -> Optional[Subscription]:
    """
    Update a subscription and record the change in history
    
    Args:
        db: Database session
        user_id: User ID
        action: Action type (updated, cancelled, etc.)
        updates: Dictionary of fields to update
        
    Returns:
        Updated subscription or None if not found
    """
    subscription = get_user_subscription(db, user_id)
    
    if not subscription:
        return None
    
    # Store previous values for history
    previous_plan = subscription.plan
    previous_status = "active" if subscription.is_active else "inactive"
    
    # Update subscription
    for key, value in updates.items():
        if hasattr(subscription, key):
            setattr(subscription, key, value)
    
    # Record in history
    record_subscription_history(
        db=db,
        user_id=user_id,
        subscription_id=subscription.id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        plan=subscription.plan,
        previous_plan=previous_plan,
        action=action,
        status="active" if subscription.is_active else "inactive",
        metadata={
            "updates": {k: str(v) for k, v in updates.items()},
            "previous_status": previous_status
        }
    )
    
    db.commit()
    db.refresh(subscription)
    
    return subscription

def process_planned_downgrades(db: Session) -> int:
    """
    Process subscriptions with planned downgrades that have reached their end date
    
    Args:
        db: Database session
        
    Returns:
        Number of subscriptions processed
    """
    # Find subscriptions with planned downgrades and end dates in the past
    subscriptions = db.query(Subscription).filter(
        Subscription.planned_downgrade_to.isnot(None),
        Subscription.is_active == True,
        Subscription.end_date <= func.now()
    ).all()
    
    count = 0
    
    for subscription in subscriptions:
        # Get plan details from pricing tiers
        from app.payment.stripe_handler import PRICING_TIERS
        
        # Process the downgrade
        previous_plan = subscription.plan
        new_plan = subscription.planned_downgrade_to
        
        # Update subscription
        subscription.plan = new_plan
        subscription.planned_downgrade_to = None
        
        # Update limits if the plan exists in PRICING_TIERS
        if new_plan in PRICING_TIERS:
            subscription.conversion_limit = PRICING_TIERS[new_plan]["limits"]["conversion_limit"]
            subscription.file_size_limit_mb = PRICING_TIERS[new_plan]["limits"]["file_size_limit_mb"]
        
        # Record in history
        record_subscription_history(
            db=db,
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            plan=new_plan,
            previous_plan=previous_plan,
            action="downgraded",
            status="active",
            metadata={
                "downgrade_processed": True,
                "effective_date": datetime.now().isoformat()
            }
        )
        
        count += 1
    
    db.commit()
    return count

def record_subscription_history(
    db: Session,
    user_id: str,
    subscription_id: str,
    stripe_subscription_id: Optional[str],
    plan: str,
    previous_plan: Optional[str],
    action: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> SubscriptionHistory:
    """
    Record a subscription history entry
    
    Args:
        db: Database session
        user_id: User ID
        subscription_id: Subscription ID
        stripe_subscription_id: Stripe subscription ID (optional)
        plan: Current plan
        previous_plan: Previous plan (optional)
        action: Action type (created, updated, cancelled, etc.)
        status: Status of the subscription
        metadata: Additional metadata (optional)
        
    Returns:
        The created subscription history entry
    """
    history_entry = SubscriptionHistory(
        user_id=user_id,
        subscription_id=subscription_id,
        stripe_subscription_id=stripe_subscription_id,
        plan=plan,
        previous_plan=previous_plan,
        action=action,
        status=status,
        metadata=metadata or {}
    )
    
    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)
    
    return history_entry

def get_subscription_history(
    db: Session,
    user_id: str,
    limit: int = 10
) -> List[SubscriptionHistory]:
    """
    Get subscription history for a user
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of entries to return
        
    Returns:
        List of subscription history entries
    """
    return db.query(SubscriptionHistory)\
        .filter(SubscriptionHistory.user_id == user_id)\
        .order_by(SubscriptionHistory.action_date.desc())\
        .limit(limit)\
        .all()

def update_subscription_with_history(
    db: Session,
    user_id: str,
    action: str,
    updates: Dict[str, Any]
) -> Optional[Subscription]:
    """
    Update a subscription and record the change in history
    
    Args:
        db: Database session
        user_id: User ID
        action: Action type (updated, cancelled, etc.)
        updates: Dictionary of fields to update
        
    Returns:
        Updated subscription or None if not found
    """
    subscription = get_user_subscription(db, user_id)
    
    if not subscription:
        return None
    
    # Store previous values for history
    previous_plan = subscription.plan
    previous_status = "active" if subscription.is_active else "inactive"
    
    # Update subscription
    for key, value in updates.items():
        if hasattr(subscription, key):
            setattr(subscription, key, value)
    
    # Record in history
    record_subscription_history(
        db=db,
        user_id=user_id,
        subscription_id=subscription.id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        plan=subscription.plan,
        previous_plan=previous_plan,
        action=action,
        status="active" if subscription.is_active else "inactive",
        metadata={
            "updates": {k: str(v) for k, v in updates.items()},
            "previous_status": previous_status
        }
    )
    
    db.commit()
    db.refresh(subscription)
    
    return subscription

def process_planned_downgrades(db: Session) -> int:
    """
    Process subscriptions with planned downgrades that have reached their end date
    
    Args:
        db: Database session
        
    Returns:
        Number of subscriptions processed
    """
    # Find subscriptions with planned downgrades and end dates in the past
    subscriptions = db.query(Subscription).filter(
        Subscription.planned_downgrade_to.isnot(None),
        Subscription.is_active == True,
        Subscription.end_date <= func.now()
    ).all()
    
    count = 0
    
    for subscription in subscriptions:
        # Get plan details from pricing tiers
        from app.payment.stripe_handler import PRICING_TIERS
        
        # Process the downgrade
        previous_plan = subscription.plan
        new_plan = subscription.planned_downgrade_to
        
        # Update subscription
        subscription.plan = new_plan
        subscription.planned_downgrade_to = None
        
        # Update limits if the plan exists in PRICING_TIERS
        if new_plan in PRICING_TIERS:
            subscription.conversion_limit = PRICING_TIERS[new_plan]["limits"]["conversion_limit"]
            subscription.file_size_limit_mb = PRICING_TIERS[new_plan]["limits"]["file_size_limit_mb"]
        
        # Record in history
        record_subscription_history(
            db=db,
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            plan=new_plan,
            previous_plan=previous_plan,
            action="downgraded",
            status="active",
            metadata={
                "downgrade_processed": True,
                "effective_date": datetime.now().isoformat()
            }
        )
        
        count += 1
    
    db.commit()
    return count

def get_user_login_history(db: Session, user_id: str, limit: int = 10) -> List[LoginHistory]:
    """
    Get a user's login history
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of records to return
        
    Returns:
        List of login history records
    """
    return db.query(LoginHistory)\
        .filter(LoginHistory.user_id == user_id)\
        .order_by(desc(LoginHistory.login_time))\
        .limit(limit)\
        .all()