"""
app/payment/stripe_handler.py - Stripe payment integration
"""
import stripe
from typing import Dict, Any, Optional
import logging
import os
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Initialize Stripe with your API key
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Define pricing tiers
PRICING_TIERS = {
    "basic": {
        "name": "Basic Plan",
        "price_id": os.environ.get("STRIPE_BASIC_PRICE_ID"),
        "amount": 999,  # $9.99
        "currency": "usd",
        "features": ["100 conversions per month", "5MB file size limit", "API access"]
    },
    "pro": {
        "name": "Pro Plan",
        "price_id": os.environ.get("STRIPE_PRO_PRICE_ID"),
        "amount": 2499,  # $24.99
        "currency": "usd",
        "features": ["500 conversions per month", "50MB file size limit", "Priority support"]
    },
    "enterprise": {
        "name": "Enterprise Plan",
        "price_id": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID"),
        "amount": 9999,  # $99.99
        "currency": "usd",
        "features": ["Unlimited conversions", "500MB file size limit", "Custom integrations"]
    }
}

def create_checkout_session(tier: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for the specified tier
    
    Args:
        tier: The pricing tier (basic, pro, enterprise)
        success_url: URL to redirect on successful payment
        cancel_url: URL to redirect on cancelled payment
        
    Returns:
        Dict containing the session ID and URL
    """
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe API key not configured")
    
    if tier not in PRICING_TIERS:
        raise HTTPException(status_code=400, detail="Invalid pricing tier")
    
    tier_info = PRICING_TIERS[tier]
    
    try:
        # Create the checkout session
        if tier_info.get("price_id"):
            # Use price ID if available (recommended for subscriptions)
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price": tier_info["price_id"],
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
            )
        else:
            # Use one-time payment as fallback
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": tier_info["currency"],
                        "product_data": {
                            "name": tier_info["name"],
                        },
                        "unit_amount": tier_info["amount"],
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
            )
        
        return {
            "session_id": checkout_session.id,
            "checkout_url": checkout_session.url
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

def verify_webhook_signature(payload: bytes, signature: str, endpoint_secret: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify and process a Stripe webhook
    
    Args:
        payload: The raw request body
        signature: The Stripe signature header
        endpoint_secret: The webhook endpoint secret
        
    Returns:
        The verified event object
    """
    if not endpoint_secret:
        endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    if not endpoint_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=endpoint_secret
        )
        return event
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid Stripe payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")

def handle_subscription_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process subscription-related events from Stripe webhooks
    
    Args:
        event: The Stripe event object
        
    Returns:
        Dict with status and details
    """
    event_type = event["type"]
    
    if event_type == "customer.subscription.created":
        subscription = event["data"]["object"]
        # Handle new subscription
        return {
            "status": "success",
            "action": "subscription_created",
            "subscription_id": subscription["id"],
            "customer_id": subscription["customer"]
        }
    
    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        # Handle subscription update
        return {
            "status": "success",
            "action": "subscription_updated",
            "subscription_id": subscription["id"],
            "customer_id": subscription["customer"]
        }
    
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        # Handle subscription cancellation
        return {
            "status": "success",
            "action": "subscription_cancelled",
            "subscription_id": subscription["id"],
            "customer_id": subscription["customer"]
        }
    
    elif event_type == "invoice.paid":
        invoice = event["data"]["object"]
        # Handle successful payment
        return {
            "status": "success",
            "action": "payment_succeeded",
            "invoice_id": invoice["id"],
            "customer_id": invoice["customer"]
        }
    
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        # Handle failed payment
        return {
            "status": "warning",
            "action": "payment_failed",
            "invoice_id": invoice["id"],
            "customer_id": invoice["customer"]
        }
    
    # Return info for any other events
    return {
        "status": "info",
        "action": "other_event",
        "event_type": event_type
    }