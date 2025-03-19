"""
app/api/payment_routes.py - Payment and subscription routes
"""
from fastapi import APIRouter, Depends, Request, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Optional, Dict, Any
import os
import logging
import stripe

from app.models.users import User
from app.auth.handlers import get_current_active_user
from app.payment.stripe_handler import (
    create_checkout_session,
    verify_webhook_signature,
    handle_subscription_event,
    PRICING_TIERS
)

# Initialize Stripe with API key from environment variable
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

router = APIRouter(prefix="/api/payment", tags=["payment"])

@router.get("/plans")
async def get_plans() -> Dict[str, Any]:
    """Get available subscription plans"""
    return {
        "plans": PRICING_TIERS
    }

@router.post("/create-checkout")
async def create_checkout(
    tier: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Create a Stripe checkout session for the specified plan"""
    # Base URLs for success and cancel redirects
    base_url = str(request.base_url).rstrip('/')
    
    success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/payment/cancel"
    
    # Create checkout session
    checkout = create_checkout_session(
        tier=tier,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    return {
        "session_id": checkout["session_id"],
        "checkout_url": checkout["checkout_url"]
    }

@router.get("/success")
async def payment_success(session_id: str) -> RedirectResponse:
    """Handle successful payment redirect"""
    # In a real application, you would verify the session and update the user's subscription
    # For now, just redirect to a success page
    return RedirectResponse(url="/payment/thank-you")

@router.get("/cancel")
async def payment_cancel() -> RedirectResponse:
    """Handle cancelled payment redirect"""
    return RedirectResponse(url="/pricing")

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None)
) -> JSONResponse:
    """Handle Stripe webhook events"""
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    
    # Get the raw request body
    payload = await request.body()
    
    # Verify the webhook signature
    event = verify_webhook_signature(payload, stripe_signature)
    
    # Handle the event
    result = handle_subscription_event(event)
    
    # In a real application, you would update the user's subscription status in your database
    # based on the event data
    
    return JSONResponse(content=result)

@router.get("/subscription", response_model=Dict[str, Any])
async def get_subscription(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Get current user's subscription details"""
    return {
        "subscription": current_user.subscription.dict(),
        "user": {
            "email": current_user.email,
            "id": current_user.id
        }
    }

@router.post("/cancel-subscription")
async def cancel_subscription(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Cancel the current user's subscription"""
    # In a real application, you would call Stripe API to cancel the subscription
    # For now, just return a success message
    return {
        "status": "success",
        "message": "Subscription cancelled successfully"
    }
