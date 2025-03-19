"""
tests/test_stripe_integration.py - Test script for Stripe integration
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions to test
from app.payment.stripe_handler import (
    create_checkout_session,
    verify_webhook_signature, 
    handle_subscription_event,
    get_subscription_details,
    cancel_subscription
)

class TestStripeIntegration(unittest.TestCase):
    """Test cases for Stripe integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock for stripe module
        self.stripe_mock = MagicMock()
        self.checkout_mock = MagicMock()
        self.customer_mock = MagicMock()
        self.subscription_mock = MagicMock()
        self.price_mock = MagicMock()
        self.product_mock = MagicMock()
        self.webhook_mock = MagicMock()
        
        # Configure mocks
        self.checkout_mock.id = "cs_test_123"
        self.checkout_mock.url = "https://checkout.stripe.com/test"
        
        self.stripe_mock.checkout.Session.create.return_value = self.checkout_mock
        
        self.customer_mock.id = "cus_123"
        self.stripe_mock.Customer.list.return_value.data = [self.customer_mock]
        self.stripe_mock.Customer.create.return_value = self.customer_mock
        
        self.subscription_mock.id = "sub_123"
        self.subscription_mock.status = "active"
        self.subscription_mock.current_period_start = int(datetime.now().timestamp())
        self.subscription_mock.current_period_end = int((datetime.now() + timedelta(days=30)).timestamp())
        self.subscription_mock.cancel_at_period_end = False
        self.subscription_mock.customer = "cus_123"
        self.subscription_mock.items.data = [MagicMock()]
        self.subscription_mock.items.data[0].price = self.price_mock
        
        self.price_mock.id = "price_123"
        self.price_mock.unit_amount = 2499  # $24.99
        self.price_mock.currency = "usd"
        self.price_mock.product = "prod_123"
        
        self.product_mock.id = "prod_123"
        self.product_mock.name = "Pro Plan"
        
        self.stripe_mock.Subscription.retrieve.return_value = self.subscription_mock
        self.stripe_mock.Product.retrieve.return_value = self.product_mock
        
        self.event_mock = {
            "type": "customer.subscription.created",
            "data": {
                "object": self.subscription_mock
            }
        }
        self.stripe_mock.Webhook.construct_event.return_value = self.event_mock
    
    @patch('app.payment.stripe_handler.stripe')
    def test_create_checkout_session(self, stripe_mock):
        """Test creating a checkout session"""
        # Configure mock
        stripe_mock.checkout.Session.create.return_value = self.checkout_mock
        stripe_mock.Customer.list.return_value.data = [self.customer_mock]
        
        # Call the function
        result = create_checkout_session(
            email="test@example.com",
            tier="pro",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_name="Test User"
        )
        
        # Check the result
        self.assertEqual(result["session_id"], "cs_test_123")
        self.assertEqual(result["checkout_url"], "https://checkout.stripe.com/test")
        
        # Verify the mock was called correctly
        stripe_mock.checkout.Session.create.assert_called_once()
    
    @patch('app.payment.stripe_handler.stripe')
    def test_verify_webhook_signature(self, stripe_mock):
        """Test verifying webhook signature"""
        # Configure mock
        stripe_mock.Webhook.construct_event.return_value = self.event_mock
        
        # Call the function
        result = verify_webhook_signature(b"payload", "signature")
        
        # Check the result
        self.assertEqual(result, self.event_mock)
        
        # Verify the mock was called correctly
        stripe_mock.Webhook.construct_event.assert_called_once()
    
    @patch('app.payment.stripe_handler.stripe')
    def test_handle_subscription_event(self, stripe_mock):
        """Test handling subscription events"""
        # Configure mock
        self.subscription_mock.items.data[0].price.id = "price_pro"
        
        # Call the function
        result = handle_subscription_event(self.event_mock)
        
        # Check the result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "subscription_created")
        self.assertEqual(result["subscription_id"], "sub_123")
    
    @patch('app.payment.stripe_handler.stripe')
    def test_get_subscription_details(self, stripe_mock):
        """Test getting subscription details"""
        # Configure mocks
        stripe_mock.Subscription.retrieve.return_value = self.subscription_mock
        stripe_mock.Product.retrieve.return_value = self.product_mock
        
        # Call the function
        result = get_subscription_details("sub_123")
        
        # Check the result
        self.assertEqual(result["id"], "sub_123")
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["product_name"], "Pro Plan")
    
    @patch('app.payment.stripe_handler.stripe')
    def test_cancel_subscription(self, stripe_mock):
        """Test cancelling a subscription"""
        # Configure mock
        stripe_mock.Subscription.modify.return_value = self.subscription_mock
        
        # Call the function
        result = cancel_subscription("sub_123", False)
        
        # Check the result
        self.assertEqual(result["id"], "sub_123")
        self.assertEqual(result["canceled"], True)
        
        # Verify the mock was called correctly
        stripe_mock.Subscription.modify.assert_called_once_with("sub_123", cancel_at_period_end=True)

if __name__ == '__main__':
    unittest.main()
