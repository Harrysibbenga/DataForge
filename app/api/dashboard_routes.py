"""
app/api/dashboard_routes.py - Routes for user dashboard functionality
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Path
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import os

from app.models.users import User, UserResponse
from app.auth.handlers import get_current_active_user, generate_api_key

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models for dashboard operations
class ApiKeyCreate(BaseModel):
    name: str
    read_stats: bool = False

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    created_at: datetime
    last_used: Optional[datetime] = None

class ProfileUpdate(BaseModel):
    full_name: str
    company: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class SubscriptionChange(BaseModel):
    plan: str  # 'basic', 'pro', 'enterprise'

# Dashboard routes
@router.get("/user-info")
async def get_user_info(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Get current user information for dashboard"""
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "subscription": {
            "plan": current_user.subscription.plan,
            "is_active": current_user.subscription.is_active,
            "start_date": current_user.subscription.start_date,
            "end_date": current_user.subscription.end_date,
            "conversions_used": current_user.subscription.conversion_count,
            "conversions_limit": current_user.subscription.conversion_limit
        }
    }

@router.get("/api-keys")
async def get_api_keys(current_user: User = Depends(get_current_active_user)) -> List[Dict[str, Any]]:
    """Get user's API keys"""
    # Return masked version of API keys for display (real apps would fetch from DB)
    sanitized_keys = []
    for key in current_user.api_keys:
        if key.get("is_active", True):
            # Mask the key except first and last 4 chars
            full_key = key.get("key", "")
            masked_key = f"{full_key[:8]}...{full_key[-4:]}" if len(full_key) > 12 else full_key
            
            sanitized_keys.append({
                "id": key.get("id", ""),
                "name": key.get("name", ""),
                "key": masked_key,
                "created_at": key.get("created_at", datetime.now()),
                "last_used": key.get("last_used", None)
            })
    
    return sanitized_keys

@router.post("/api-keys")
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Create a new API key for the user"""
    # Check if user has reached the API key limit for their plan
    api_key_limits = {
        "free": 1,
        "basic": 3,
        "pro": 5,
        "enterprise": 10
    }
    
    active_keys = len([k for k in current_user.api_keys if k.get("is_active", True)])
    plan = current_user.subscription.plan
    key_limit = api_key_limits.get(plan, 1)
    
    if active_keys >= key_limit:
        raise HTTPException(
            status_code=403,
            detail=f"You have reached the maximum number of API keys ({key_limit}) for your plan"
        )
    
    # Generate a new API key
    new_key = generate_api_key()
    key_id = f"key_{len(current_user.api_keys) + 1}"
    
    # In a real app, you would save this to a database
    # For now, we'll just add it to the user's api_keys list
    key_entry = {
        "id": key_id,
        "key": new_key,
        "name": key_data.name,
        "created_at": datetime.now(),
        "last_used": None,
        "is_active": True,
        "permissions": {
            "convert": True,
            "read_stats": key_data.read_stats
        }
    }
    
    current_user.api_keys.append(key_entry)
    
    # Return the full key (only time it's shown in full)
    return {
        "id": key_id,
        "key": new_key,
        "name": key_data.name,
        "created_at": key_entry["created_at"]
    }

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str = Path(...),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Revoke an API key"""
    # In a real app, you would mark the key as inactive in your database
    # For now, we'll just simulate it
    for key in current_user.api_keys:
        if key.get("id") == key_id:
            key["is_active"] = False
            break
    else:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return {"status": "success", "message": "API key revoked successfully"}

@router.get("/usage")
async def get_usage_stats(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Get user's usage statistics"""
    # In a real app, you would fetch this data from your database
    
    # Calculate billing period dates
    today = datetime.now()
    if current_user.subscription.start_date:
        billing_start = current_user.subscription.start_date
        days_in_month = 30
        billing_day = billing_start.day
        
        # Calculate next billing date
        if billing_day > today.day:
            # Next billing is this month
            next_billing = today.replace(day=billing_day)
        else:
            # Next billing is next month
            if today.month == 12:
                next_billing = today.replace(year=today.year+1, month=1, day=billing_day)
            else:
                next_billing = today.replace(month=today.month+1, day=billing_day)
    else:
        # Default if no subscription data
        billing_start = today - timedelta(days=15)
        next_billing = today + timedelta(days=15)
    
    # Calculate days left in billing period
    days_left = (next_billing - today).days
    
    return {
        "subscription": {
            "plan": current_user.subscription.plan,
            "conversions_used": current_user.subscription.conversion_count,
            "conversions_limit": current_user.subscription.conversion_limit,
            "conversions_remaining": max(0, current_user.subscription.conversion_limit - current_user.subscription.conversion_count),
            "api_requests_used": 87,  # Sample data
            "api_requests_limit": 1000,  # Sample data
            "billing_period_start": billing_start,
            "billing_period_end": next_billing,
            "days_left": days_left
        },
        "format_usage": {
            "csv_to_json": 45,
            "json_to_excel": 25,
            "excel_to_csv": 20,
            "xml_to_json": 15,
            "yaml_to_json": 10
        },
        "recent_conversions": [
            {
                "date": datetime.now() - timedelta(hours=2),
                "file": "customers.csv",
                "from_format": "CSV",
                "to_format": "JSON",
                "size": "25.4 KB",
                "source": "Web UI"
            },
            {
                "date": datetime.now() - timedelta(hours=5),
                "file": "inventory.json",
                "from_format": "JSON",
                "to_format": "Excel",
                "size": "42.1 KB",
                "source": "API"
            },
            {
                "date": datetime.now() - timedelta(days=1),
                "file": "sales_data.xlsx",
                "from_format": "Excel",
                "to_format": "CSV",
                "size": "128.7 KB",
                "source": "Web UI"
            }
        ]
    }

@router.put("/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Update user profile information"""
    # In a real app, you would update this in your database
    current_user.full_name = profile_data.full_name
    
    return {"status": "success", "message": "Profile updated successfully"}

@router.put("/password")
async def update_password(
    password_data: PasswordUpdate,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Update user password"""
    # In a real app, you would verify the current password and update in your database
    # For now, we'll just simulate a successful password change
    
    # Simple validation
    if len(password_data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long")
    
    return {"status": "success", "message": "Password updated successfully"}

@router.post("/subscription")
async def change_subscription(
    subscription_data: SubscriptionChange,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Change user subscription plan"""
    # Validate the plan
    valid_plans = ["basic", "pro", "enterprise"]
    if subscription_data.plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    current_plan = current_user.subscription.plan
    new_plan = subscription_data.plan
    
    # For downgrades, change takes effect at end of billing cycle
    if (current_plan == "enterprise" and new_plan in ["pro", "basic"]) or \
       (current_plan == "pro" and new_plan == "basic"):
        # In a real app, you would schedule this change in your database
        return {
            "status": "scheduled",
            "message": f"Your plan will be downgraded to {new_plan.capitalize()} at the end of your current billing cycle",
            "effective_date": current_user.subscription.end_date
        }
    
    # For upgrades, redirect to payment
    elif (current_plan == "basic" and new_plan in ["pro", "enterprise"]) or \
         (current_plan == "pro" and new_plan == "enterprise"):
        # In a real app, you would create a checkout session and return the URL
        stripe_price_ids = {
            "basic": os.environ.get("STRIPE_BASIC_PRICE_ID", "price_basic"),
            "pro": os.environ.get("STRIPE_PRO_PRICE_ID", "price_pro"),
            "enterprise": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise")
        }
        
        return {
            "status": "payment_required",
            "message": f"Please complete payment to upgrade to the {new_plan.capitalize()} plan",
            "checkout_url": f"/api/payment/create-checkout?tier={new_plan}"
        }
    
    # No change needed
    else:
        return {
            "status": "no_change",
            "message": f"You are already on the {new_plan.capitalize()} plan"
        }

@router.delete("/subscription")
async def cancel_subscription(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Cancel user subscription"""
    # In a real app, you would call Stripe to cancel the subscription
    
    # For now, we'll just simulate a successful cancellation
    return {
        "status": "success",
        "message": "Your subscription has been canceled and will end on your next billing date",
        "end_date": current_user.subscription.end_date
    }

@router.delete("/account")
async def delete_account(current_user: User = Depends(get_current_active_user)) -> Dict[str, str]:
    """Delete user account"""
    # In a real app, you would:
    # 1. Cancel subscriptions
    # 2. Revoke all API keys
    # 3. Delete user data
    # 4. Remove user from database
    
    # For now, we'll just simulate a successful deletion
    return {"status": "success", "message": "Your account has been deleted"}
