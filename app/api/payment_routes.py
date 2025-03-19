"""
app/api/payment_routes.py - Complete payment and subscription routes
"""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Response
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Optional, Dict, Any
import os
import logging
from sqlalchemy.orm import Session

from app.db.config import get_db
import app.db.crud as crud
from app.db.models import User
from app.auth.handlers import get_current_active_user
from app.payment.stripe_handler import (
    PRICING_TIERS,
    create_checkout_session,
    verify_webhook_signature,
    handle_subscription_event,
    get_subscription_details,
    cancel_subscription,
    change_subscription_plan
)

router = APIRouter(prefix="/api/payment", tags=["payment"])
logger = logging.getLogger(__name__)

@router.get("/plans")
async def get_plans() -> Dict[str, Any]:
    """Get available subscription plans"""
    # Remove pricing IDs and other internal details before returning
    formatted_tiers = {}
    for tier, details in PRICING_TIERS.items():
        formatted_tiers[tier] = {
            "name": details["name"],
            "amount": details["amount"] / 100,  # Convert cents to dollars
            "currency": details["currency"],
            "features": details["features"],
            "limits": details["limits"]
        }
        
    return {
        "plans": formatted_tiers
    }

@router.post("/create-checkout")
async def create_checkout(
    tier: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a Stripe checkout session for the specified plan"""
    # Base URLs for success and cancel redirects
    base_url = str(request.base_url).rstrip('/')
    
    success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/payment/cancel"
    
    try:
        # Create checkout session
        checkout = create_checkout_session(
            email=current_user.email,
            tier=tier,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_name=current_user.full_name
        )
        
        # Record the checkout attempt in database
        checkout_record = {
            "user_id": current_user.id,
            "tier": tier,
            "session_id": checkout["session_id"],
            "status": "created"
        }
        # In a real application, you'd save this to a database table
        # For now, just log it
        logger.info(f"Checkout created: {checkout_record}")
        
        return {
            "session_id": checkout["session_id"],
            "checkout_url": checkout["checkout_url"]
        }
    
    except Exception as e:
        logger.error(f"Error creating checkout: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/success")
async def payment_success(
    session_id: str,
    db: Session = Depends(get_db)
) -> RedirectResponse:
    """Handle successful payment redirect"""
    try:
        # Verify the checkout session
        session = None
        
        try:
            import stripe
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            logger.error(f"Error retrieving session: {str(e)}")
            # Continue with redirect even if verification fails
        
        if session and session.get("subscription"):
            # Update user's subscription in database
            subscription_id = session.get("subscription")
            client_ref = session.get("client_reference_id")  # Should contain email
            
            # Find user by email
            if client_ref:
                user = crud.get_user_by_email(db, client_ref)
                if user:
                    # Get plan details from subscription
                    sub_details = get_subscription_details(subscription_id)
                    plan = sub_details.get("plan", "basic")
                    end_date = sub_details.get("current_period_end")
                    
                    # Update user's subscription in the database
                    subscription = crud.get_user_subscription(db, user.id)
                    if subscription:
                        # Update existing subscription
                        subscription.plan = plan
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = session.get("customer")
                        subscription.is_active = True
                        subscription.end_date = end_date
                        subscription.conversion_limit = PRICING_TIERS[plan]["limits"]["conversion_limit"]
                        subscription.file_size_limit_mb = PRICING_TIERS[plan]["limits"]["file_size_limit_mb"]
                        db.commit()
                    else:
                        # Create new subscription (unlikely but handle it)
                        crud.create_subscription(db, user.id, plan)
                        
                    logger.info(f"Updated subscription for user {user.id} to {plan}")
        
        # Redirect to thank you page
        return RedirectResponse(url="/payment/thank-you")
    
    except Exception as e:
        logger.error(f"Error in payment success handler: {str(e)}")
        # Redirect anyway to avoid breaking the user flow
        return RedirectResponse(url="/payment/thank-you")

@router.get("/cancel")
async def payment_cancel() -> RedirectResponse:
    """Handle cancelled payment redirect"""
    return RedirectResponse(url="/pricing")

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None)
) -> JSONResponse:
    """Handle Stripe webhook events"""
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    
    # Get the raw request body
    payload = await request.body()
    
    try:
        # Verify the webhook signature
        event = verify_webhook_signature(payload, stripe_signature)
        
        # Process the event
        result = handle_subscription_event(event)
        
        # Handle database updates based on the event
        if result["action"] == "subscription_created" or result["action"] == "subscription_updated":
            # Update user subscription in database
            # First, find the user by customer ID
            db = next(get_db())
            
            try:
                # Try to find the subscription in the database
                subscription_id = result.get("subscription_id")
                plan = result.get("plan", "basic")
                customer_id = result.get("customer_id")
                client_ref = result.get("client_reference")
                
                # Find user by customer ID or email reference
                user = None
                if client_ref and "@" in client_ref:  # Looks like an email
                    user = crud.get_user_by_email(db, client_ref)
                
                if user:
                    # Update the subscription
                    subscription = crud.get_user_subscription(db, user.id)
                    if subscription:
                        subscription.plan = plan
                        subscription.stripe_subscription_id = subscription_id
                        subscription.stripe_customer_id = customer_id
                        subscription.is_active = True
                        
                        # Update limits based on plan
                        if plan in PRICING_TIERS:
                            subscription.conversion_limit = PRICING_TIERS[plan]["limits"]["conversion_limit"]
                            subscription.file_size_limit_mb = PRICING_TIERS[plan]["limits"]["file_size_limit_mb"]
                        
                        db.commit()
                        logger.info(f"Updated subscription for user {user.id}")
            except Exception as e:
                logger.error(f"Error updating subscription in database: {str(e)}")
        
        elif result["action"] == "subscription_cancelled":
            # Mark subscription as inactive
            db = next(get_db())
            
            try:
                subscription_id = result.get("subscription_id")
                # Find subscription by Stripe subscription ID
                subscriptions = db.query(User).join(User.subscription).filter(
                    User.subscription.has(stripe_subscription_id=subscription_id)
                ).all()
                
                for user in subscriptions:
                    if user.subscription:
                        user.subscription.is_active = False
                        user.subscription.plan = "free"  # Downgrade to free
                        db.commit()
                        logger.info(f"Marked subscription inactive for user {user.id}")
            except Exception as e:
                logger.error(f"Error marking subscription inactive: {str(e)}")
        
        # Return a success response to Stripe
        return JSONResponse(content={"status": "success"})
    
    except HTTPException as e:
        logger.error(f"Webhook error: {e.detail}")
        # Return the error to Stripe
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)
    
    except Exception as e:
        logger.error(f"Unhandled error in webhook: {str(e)}")
        return JSONResponse(content={"error": "Internal server error"}, status_code=500)

@router.get("/subscription")
async def get_user_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get current user's subscription details"""
    subscription = crud.get_user_subscription(db, current_user.id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get additional details from Stripe if a Stripe subscription ID exists
    stripe_details = {}
    if subscription.stripe_subscription_id:
        try:
            stripe_details = get_subscription_details(subscription.stripe_subscription_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe subscription: {str(e)}")
            # Continue without Stripe details
    
    response = {
        "subscription": {
            "id": subscription.id,
            "plan": subscription.plan,
            "is_active": subscription.is_active,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "conversion_count": subscription.conversion_count,
            "conversion_limit": subscription.conversion_limit,
            "file_size_limit_mb": subscription.file_size_limit_mb
        },
        "stripe": stripe_details,
        "user": {
            "id": current_user.id,
            "email": current_user.email
        }
    }
    
    # Add feature details from pricing tiers
    if subscription.plan in PRICING_TIERS:
        response["features"] = PRICING_TIERS[subscription.plan].get("features", [])
    
    return response

@router.post("/cancel-subscription")
async def cancel_user_subscription(
    at_period_end: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cancel the current user's subscription
    
    Args:
        at_period_end: If True, cancel at the end of the billing period; 
                      if False, cancel immediately
    """
    subscription = crud.get_user_subscription(db, current_user.id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    if not subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription found")
    
    try:
        # Cancel in Stripe
        result = cancel_subscription(
            subscription_id=subscription.stripe_subscription_id,
            cancel_immediately=not at_period_end
        )
        
        # Update in database
        if not at_period_end:
            # Immediate cancellation
            subscription.is_active = False
            subscription.plan = "free"
            # Reset limits
            subscription.conversion_limit = PRICING_TIERS["free"]["limits"]["conversion_limit"]
            subscription.file_size_limit_mb = PRICING_TIERS["free"]["limits"]["file_size_limit_mb"]
        else:
            # Will be cancelled at period end, mark in the database
            # The webhook will handle the actual status change later
            pass
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Subscription cancelled successfully",
            "cancel_at_period_end": at_period_end,
            "details": result
        }
    
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription cancellation error: {str(e)}")

@router.post("/change-plan")
async def change_subscription_plan_endpoint(
    new_plan: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Change the user's subscription plan
    
    Args:
        new_plan: New plan tier (basic, pro, enterprise)
    """
    if new_plan not in PRICING_TIERS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    subscription = crud.get_user_subscription(db, current_user.id)
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # If no Stripe subscription exists, create a new checkout session
    if not subscription.stripe_subscription_id or not subscription.is_active:
        # Redirect to checkout
        return {
            "status": "redirect",
            "message": "No active subscription found. Please complete checkout.",
            "action": "checkout",
            "plan": new_plan
        }
    
    # If downgrading, handle differently (usually at period end)
    current_plan = subscription.plan
    current_plan_index = list(PRICING_TIERS.keys()).index(current_plan) if current_plan in PRICING_TIERS else -1
    new_plan_index = list(PRICING_TIERS.keys()).index(new_plan) if new_plan in PRICING_TIERS else -1
    
    is_downgrade = current_plan_index > new_plan_index
    
    try:
        if is_downgrade:
            # Downgrades typically take effect at the end of the billing period
            # Just record the intent in the database
            subscription.planned_downgrade_to = new_plan
            db.commit()
            
            return {
                "status": "scheduled",
                "message": f"Your plan will be downgraded to {new_plan} at the end of your current billing period.",
                "effective_date": subscription.end_date
            }
        
        # For upgrades, process immediately
        result = change_subscription_plan(
            subscription_id=subscription.stripe_subscription_id,
            new_plan=new_plan
        )
        
        # Update the database with new plan details
        subscription.plan = new_plan
        subscription.conversion_limit = PRICING_TIERS[new_plan]["limits"]["conversion_limit"]
        subscription.file_size_limit_mb = PRICING_TIERS[new_plan]["limits"]["file_size_limit_mb"]
        db.commit()
        
        return {
            "status": "success",
            "message": f"Your subscription has been upgraded to {new_plan}.",
            "details": result
        }
    
    except Exception as e:
        logger.error(f"Error changing subscription plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription modification error: {str(e)}")