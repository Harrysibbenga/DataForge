"""
app/payment/stripe_handler.py - Enhanced Stripe payment integration
"""
import stripe
from typing import Dict, Any, Optional, List
import logging
import os
from fastapi import HTTPException
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Initialize Stripe with your API key
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Define pricing tiers and their details
PRICING_TIERS = {
    "basic": {
        "name": "Basic Plan",
        "price_id": os.environ.get("STRIPE_BASIC_PRICE_ID"),
        "amount": 999,  # $9.99
        "currency": "usd",
        "features": ["100 conversions per month", "50MB file size limit", "API access"],
        "limits": {
            "conversion_limit": 100,
            "file_size_limit_mb": 50,
            "api_keys_limit": 3
        }
    },
    "pro": {
        "name": "Pro Plan",
        "price_id": os.environ.get("STRIPE_PRO_PRICE_ID"),
        "amount": 2499,  # $24.99
        "currency": "usd",
        "features": ["500 conversions per month", "100MB file size limit", "Priority support"],
        "limits": {
            "conversion_limit": 500,
            "file_size_limit_mb": 100,
            "api_keys_limit": 5
        }
    },
    "enterprise": {
        "name": "Enterprise Plan",
        "price_id": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID"),
        "amount": 9999,  # $99.99
        "currency": "usd",
        "features": ["Unlimited conversions", "500MB file size limit", "Dedicated support"],
        "limits": {
            "conversion_limit": 9999,  # Effectively unlimited
            "file_size_limit_mb": 500,
            "api_keys_limit": 10
        }
    }
}

def get_stripe_customer(email: str, name: Optional[str] = None) -> str:
    """
    Get or create a Stripe customer for the given email
    
    Args:
        email: Customer email
        name: Customer name (optional)
        
    Returns:
        Stripe customer ID
    """
    try:
        # Search for existing customer
        customers = stripe.Customer.list(email=email, limit=1)
        
        if customers and customers.data:
            # Return existing customer ID
            return customers.data[0].id
        
        # Create new customer
        customer = stripe.Customer.create(
            email=email,
            name=name
        )
        return customer.id
    
    except stripe.error.StripeError as e:
        logger.error(f"Error creating/retrieving Stripe customer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment processing error: {str(e)}")

def create_checkout_session(
    email: str, 
    tier: str, 
    success_url: str, 
    cancel_url: str,
    customer_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for the specified tier
    
    Args:
        email: Customer email
        tier: The pricing tier (basic, pro, enterprise)
        success_url: URL to redirect on successful payment
        cancel_url: URL to redirect on cancelled payment
        customer_name: Customer name (optional)
        
    Returns:
        Dict containing the session ID and URL
    """
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe API key not configured")
    
    if tier not in PRICING_TIERS:
        raise HTTPException(status_code=400, detail="Invalid pricing tier")
    
    tier_info = PRICING_TIERS[tier]
    
    try:
        # Get or create customer
        customer_id = get_stripe_customer(email, customer_name)
        
        # Create the checkout session
        if tier_info.get("price_id"):
            # Use price ID if available (recommended for subscriptions)
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": tier_info["price_id"],
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=email,  # Store email as reference
                metadata={
                    "plan": tier,
                    "customer_email": email
                }
            )
        else:
            # Fallback to one-time payment if price_id not available
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": tier_info["currency"],
                        "product_data": {
                            "name": tier_info["name"],
                        },
                        "unit_amount": tier_info["amount"],
                        "recurring": {
                            "interval": "month"
                        }
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=email,
                metadata={
                    "plan": tier,
                    "customer_email": email
                }
            )
        
        return {
            "session_id": checkout_session.id,
            "checkout_url": checkout_session.url
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment processing error: {str(e)}")

def get_subscription_details(subscription_id: str) -> Dict[str, Any]:
    """
    Get details of a Stripe subscription
    
    Args:
        subscription_id: Stripe subscription ID
        
    Returns:
        Dict with subscription details
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Get the plan/price details
        price = subscription.items.data[0].price
        product = stripe.Product.retrieve(price.product)
        
        # Determine plan tier by comparing with known price IDs
        plan_tier = "unknown"
        for tier, info in PRICING_TIERS.items():
            if info.get("price_id") == price.id:
                plan_tier = tier
                break
        
        # Calculate end date
        current_period_end = datetime.fromtimestamp(subscription.current_period_end)
        
        return {
            "id": subscription.id,
            "status": subscription.status,
            "plan": plan_tier,
            "product_name": product.name,
            "amount": price.unit_amount / 100,  # Convert cents to dollars
            "currency": price.currency,
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start),
            "current_period_end": current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "customer_id": subscription.customer
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Error retrieving subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription retrieval error: {str(e)}")

def cancel_subscription(subscription_id: str, cancel_immediately: bool = False) -> Dict[str, Any]:
    """
    Cancel a Stripe subscription
    
    Args:
        subscription_id: Stripe subscription ID
        cancel_immediately: If True, cancel immediately; if False, cancel at period end
        
    Returns:
        Dict with cancellation details
    """
    try:
        if cancel_immediately:
            # Cancel immediately
            subscription = stripe.Subscription.delete(subscription_id)
        else:
            # Cancel at period end
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        
        return {
            "id": subscription.id,
            "status": subscription.status,
            "canceled": True,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription cancellation error: {str(e)}")

def change_subscription_plan(subscription_id: str, new_plan: str) -> Dict[str, Any]:
    """
    Change a subscription to a new plan
    
    Args:
        subscription_id: Stripe subscription ID
        new_plan: New plan tier (basic, pro, enterprise)
        
    Returns:
        Dict with updated subscription details
    """
    if new_plan not in PRICING_TIERS:
        raise HTTPException(status_code=400, detail="Invalid plan tier")
    
    try:
        # Get the current subscription
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Get the new price ID
        new_price_id = PRICING_TIERS[new_plan]["price_id"]
        
        if not new_price_id:
            raise HTTPException(status_code=500, detail="Price ID not configured for selected plan")
        
        # Update the subscription with the new price
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{
                'id': subscription['items']['data'][0].id,
                'price': new_price_id,
            }],
            proration_behavior='always_invoice',  # You can adjust this as needed
            metadata={"plan": new_plan}
        )
        
        return get_subscription_details(updated_subscription.id)
    
    except stripe.error.StripeError as e:
        logger.error(f"Error changing subscription plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription modification error: {str(e)}")

def verify_webhook_signature(payload: bytes, signature: str) -> Dict[str, Any]:
    """
    Verify and process a Stripe webhook
    
    Args:
        payload: The raw request body
        signature: The Stripe signature header
        
    Returns:
        The verified event object
    """
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=WEBHOOK_SECRET
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
    
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Check if this is a subscription checkout
        if session.get("mode") == "subscription":
            # Extract subscription ID and customer information
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")
            client_ref = session.get("client_reference_id")
            plan = session.get("metadata", {}).get("plan")
            
            return {
                "status": "success",
                "action": "subscription_created",
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "client_reference": client_ref,
                "plan": plan
            }
    
    elif event_type == "customer.subscription.created":
        subscription = event["data"]["object"]
        
        # Get subscription details
        plan = "unknown"
        for tier, info in PRICING_TIERS.items():
            if info.get("price_id") == subscription.items.data[0].price.id:
                plan = tier
                break
                
        return {
            "status": "success",
            "action": "subscription_created",
            "subscription_id": subscription.id,
            "customer_id": subscription.customer,
            "plan": plan,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }
    
    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        
        # Get subscription details
        plan = "unknown"
        for tier, info in PRICING_TIERS.items():
            if info.get("price_id") == subscription.items.data[0].price.id:
                plan = tier
                break
                
        return {
            "status": "success",
            "action": "subscription_updated",
            "subscription_id": subscription.id,
            "customer_id": subscription.customer,
            "plan": plan,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }
    
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        
        return {
            "status": "success",
            "action": "subscription_cancelled",
            "subscription_id": subscription.id,
            "customer_id": subscription.customer
        }
    
    elif event_type == "invoice.paid":
        invoice = event["data"]["object"]
        
        # Extract subscription info if available
        subscription_id = invoice.get("subscription")
        subscription_details = {}
        
        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)
                subscription_details = {
                    "subscription_id": subscription_id,
                    "plan": subscription.metadata.get("plan", "unknown"),
                    "current_period_end": datetime.fromtimestamp(subscription.current_period_end)
                }
            except Exception as e:
                logger.error(f"Error retrieving subscription: {str(e)}")
        
        return {
            "status": "success",
            "action": "payment_succeeded",
            "invoice_id": invoice.id,
            "customer_id": invoice.customer,
            "amount_paid": invoice.amount_paid / 100,  # Convert cents to dollars
            "subscription": subscription_details
        }
    
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        
        return {
            "status": "warning",
            "action": "payment_failed",
            "invoice_id": invoice.id,
            "customer_id": invoice.customer,
            "subscription_id": invoice.get("subscription"),
            "attempt_count": invoice.get("attempt_count", 1),
            "next_payment_attempt": invoice.get("next_payment_attempt")
        }
    
    # Return info for any other events
    return {
        "status": "info",
        "action": "other_event",
        "event_type": event_type
    }