"""
app/api/dashboard_routes.py - Dashboard routes with database integration
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import os
import stripe

from app.db.config import get_db
from app.db.models import User
import app.db.crud as crud
from app.auth.handlers import get_current_active_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models for dashboard operations
class ProfileUpdate(BaseModel):
    full_name: str
    company: Optional[str] = None

class SubscriptionChange(BaseModel):
    plan: str  # 'basic', 'pro', 'enterprise'

# Dashboard routes
@router.get("/user-info")
async def get_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user information for dashboard"""
    # Get subscription details
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get usage statistics
    usage_stats = crud.get_conversion_stats(db, current_user.id)
    
    # Calculate days left in billing period
    days_left = 0
    if subscription.end_date:
        days_left = (subscription.end_date - datetime.now()).days
        days_left = max(0, days_left)  # Ensure non-negative
    
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "company": current_user.company,
            "created_at": current_user.created_at,
            "last_login": current_user.last_login
        },
        "subscription": {
            "plan": subscription.plan,
            "is_active": subscription.is_active,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "conversions_used": subscription.conversion_count,
            "conversions_limit": subscription.conversion_limit,
            "conversions_remaining": max(0, subscription.conversion_limit - subscription.conversion_count),
            "file_size_limit_mb": subscription.file_size_limit_mb,
            "days_left": days_left
        },
        "usage": usage_stats
    }

@router.get("/usage")
async def get_usage_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get user's usage statistics"""
    # Get subscription details
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get conversion stats
    stats = crud.get_conversion_stats(db, current_user.id)
    
    # Get recent conversions
    recent_conversions = crud.get_user_conversions(db, current_user.id, limit=10)
    
    # Format recent conversions for response
    formatted_conversions = []
    for conv in recent_conversions:
        formatted_conversions.append({
            "id": conv.id,
            "date": conv.created_at,
            "file_name": conv.file_name,
            "from_format": conv.from_format,
            "to_format": conv.to_format,
            "file_size_kb": conv.file_size_kb,
            "source": conv.source,
            "status": conv.status
        })
    
    # Format statistics for response
    format_usage = {}
    for key, value in stats.get("format_distribution", {}).items():
        # Convert format names to more readable form
        from_format, to_format = key.split("_to_")
        nice_key = f"{from_format.upper()} to {to_format.upper()}"
        format_usage[nice_key] = value
    
    return {
        "subscription": {
            "plan": subscription.plan,
            "conversions_used": subscription.conversion_count,
            "conversions_limit": subscription.conversion_limit,
            "conversions_remaining": max(0, subscription.conversion_limit - subscription.conversion_count),
            "billing_period_start": subscription.start_date,
            "billing_period_end": subscription.end_date,
            "days_left": (subscription.end_date - datetime.now()).days if subscription.end_date else 0
        },
        "statistics": {
            "total_conversions": stats.get("total", 0),
            "successful_conversions": stats.get("successful", 0),
            "failed_conversions": stats.get("errors", 0),
            "web_conversions": stats.get("source_distribution", {}).get("web", 0),
            "api_conversions": stats.get("source_distribution", {}).get("api", 0)
        },
        "format_usage": format_usage,
        "recent_conversions": formatted_conversions
    }

@router.put("/profile")
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Update user profile information"""
    # Update user
    updated_user = crud.update_user(
        db=db,
        user_id=current_user.id,
        full_name=profile_data.full_name,
        company=profile_data.company
    )
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Profile updated successfully"}

@router.post("/subscription")
async def change_subscription(
    subscription_data: SubscriptionChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Change user subscription plan"""
    # Validate the plan
    valid_plans = ["basic", "pro", "enterprise"]
    if subscription_data.plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    # Get current subscription
    current_subscription = crud.get_user_subscription(db, current_user.id)
    if not current_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    current_plan = current_subscription.plan
    new_plan = subscription_data.plan
    
    # For downgrades, change takes effect at end of billing cycle
    if (current_plan == "enterprise" and new_plan in ["pro", "basic"]) or \
       (current_plan == "pro" and new_plan == "basic"):
        # Schedule the downgrade
        current_subscription.plan = new_plan  # This will be updated at end of billing cycle
        db.commit()
        
        return {
            "status": "scheduled",
            "message": f"Your plan will be downgraded to {new_plan.capitalize()} at the end of your current billing cycle",
            "effective_date": current_subscription.end_date
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
async def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Cancel user subscription"""
    # Get current subscription
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # In a real app, you would call Stripe to cancel the subscription
    
    # Mark subscription as inactive at the end of billing cycle
    subscription.is_active = False
    db.commit()
    
    return {
        "status": "success",
        "message": "Your subscription has been canceled and will end on your next billing date",
        "end_date": subscription.end_date
    }

@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Delete user account"""
    # In a real app with Stripe, you would cancel any active subscriptions
    
    # Delete the user (this will cascade to related entities)
    success = crud.delete_user(db, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Your account has been deleted"}

@router.get("/login-history")
async def get_login_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get user's login history"""
    # This would be implemented in the crud module
    # For now, return some mock data
    return [
        {
            "id": "1",
            "login_time": datetime.now() - timedelta(hours=2),
            "ip_address": "192.168.1.1",
            "device": "Chrome on Windows",
            "location": "New York, USA",
            "success": True
        },
        {
            "id": "2",
            "login_time": datetime.now() - timedelta(days=1),
            "ip_address": "192.168.1.1",
            "device": "Firefox on MacOS",
            "location": "New York, USA",
            "success": True
        }
    ]
    
@router.get("/subscription/history")
async def get_subscription_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get user's subscription history"""
    history = crud.get_subscription_history(db, current_user.id, limit)
    
    # Format for response
    result = []
    for entry in history:
        result.append({
            "id": entry.id,
            "action": entry.action,
            "action_date": entry.action_date,
            "plan": entry.plan,
            "previous_plan": entry.previous_plan,
            "status": entry.status,
            "metadata": entry.metadata
        })
    
    return result

@router.post("/subscription/downgrade")
async def downgrade_subscription(
    plan: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Schedule a subscription downgrade for the end of the billing period
    
    Args:
        plan: New plan tier (basic, free)
    """
    # Validate plan
    valid_plans = ["free", "basic"]
    if plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Invalid plan for downgrade")
    
    # Get subscription
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Check current plan
    current_plan = subscription.plan
    if current_plan in ["free", "basic"] and plan == "free":
        # Can't downgrade from basic to free
        raise HTTPException(status_code=400, detail="Cannot downgrade further")
    
    if current_plan == plan:
        return {"status": "no_change", "message": f"You are already on the {plan} plan"}
    
    # Schedule the downgrade
    subscription.planned_downgrade_to = plan
    
    # Record in history
    crud.record_subscription_history(
        db=db,
        user_id=current_user.id,
        subscription_id=subscription.id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        plan=subscription.plan,
        previous_plan=None,
        action="downgrade_scheduled",
        status="active",
        metadata={
            "downgrade_to": plan,
            "scheduled_date": datetime.now().isoformat(),
            "effective_date": subscription.end_date.isoformat() if subscription.end_date else None
        }
    )
    
    db.commit()
    
    return {
        "status": "scheduled",
        "message": f"Your plan will be downgraded to {plan} at the end of your current billing period",
        "effective_date": subscription.end_date
    }

@router.post("/subscription/cancel")
async def cancel_user_subscription(
    at_period_end: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cancel user subscription
    
    Args:
        at_period_end: If True, cancel at the end of the billing period; 
                      if False, cancel immediately
    """
    # This endpoint should redirect to the payment_routes.py implementation
    try:
        from app.api.payment_routes import cancel_user_subscription as cancel_subscription_impl
        
        # Call the implementation in payment_routes.py
        return await cancel_subscription_impl(at_period_end, current_user, db)
    
    except Exception as e:
        logging.error(f"Error canceling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/billing")
async def get_billing_details(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get user's billing details"""
    # Get subscription
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get subscription details from Stripe if available
    stripe_details = {}
    if subscription.stripe_subscription_id:
        try:
            from app.payment.stripe_handler import get_subscription_details
            stripe_details = get_subscription_details(subscription.stripe_subscription_id)
        except Exception as e:
            logging.error(f"Error retrieving Stripe subscription: {str(e)}")
            # Continue without Stripe details
    
    # Format subscription info
    subscription_info = {
        "id": subscription.id,
        "plan": subscription.plan,
        "is_active": subscription.is_active,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "conversion_count": subscription.conversion_count,
        "conversion_limit": subscription.conversion_limit,
        "file_size_limit_mb": subscription.file_size_limit_mb,
        "planned_downgrade_to": subscription.planned_downgrade_to,
    }
    
    # Get recent invoices from Stripe if available
    invoices = []
    if subscription.stripe_customer_id:
        try:
            import stripe
            stripe_invoices = stripe.Invoice.list(
                customer=subscription.stripe_customer_id,
                limit=5
            )
            
            for invoice in stripe_invoices.data:
                invoices.append({
                    "id": invoice.id,
                    "number": invoice.number,
                    "amount_due": invoice.amount_due / 100,  # Convert cents to dollars
                    "amount_paid": invoice.amount_paid / 100,
                    "currency": invoice.currency,
                    "status": invoice.status,
                    "created": datetime.fromtimestamp(invoice.created),
                    "due_date": datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
                    "hosted_invoice_url": invoice.hosted_invoice_url,
                })
        except Exception as e:
            logging.error(f"Error retrieving Stripe invoices: {str(e)}")
            # Continue without invoice details
    
    return {
        "subscription": subscription_info,
        "stripe": stripe_details,
        "invoices": invoices,
        "payment_method": None  # Would be populated with actual payment method in production
    }

@router.get("/subscription/invoices")
async def get_invoices(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get user's invoice history"""
    # Get subscription
    subscription = crud.get_user_subscription(db, current_user.id)
    if not subscription or not subscription.stripe_customer_id:
        return []
    
    # Get invoices from Stripe
    invoices = []
    try:
        import stripe
        stripe_invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id,
            limit=limit
        )
        
        for invoice in stripe_invoices.data:
            invoices.append({
                "id": invoice.id,
                "number": invoice.number,
                "amount_due": invoice.amount_due / 100,  # Convert cents to dollars
                "amount_paid": invoice.amount_paid / 100,
                "currency": invoice.currency,
                "status": invoice.status,
                "created": datetime.fromtimestamp(invoice.created),
                "due_date": datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
                "hosted_invoice_url": invoice.hosted_invoice_url,
                "invoice_pdf": invoice.invoice_pdf,
                "period_start": datetime.fromtimestamp(invoice.period_start) if invoice.period_start else None,
                "period_end": datetime.fromtimestamp(invoice.period_end) if invoice.period_end else None,
            })
    except Exception as e:
        logging.error(f"Error retrieving Stripe invoices: {str(e)}")
        # Return empty list on error
    
    return invoices