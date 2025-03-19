"""
scripts/setup_stripe.py - Script to set up Stripe products and prices
"""
import os
import argparse
import stripe
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Stripe API key from environment variable
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")

if not STRIPE_SECRET_KEY:
    print("Error: STRIPE_SECRET_KEY environment variable not set")
    exit(1)

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Define pricing tiers
PRICING_TIERS = {
    "basic": {
        "name": "Basic Plan",
        "description": "Perfect for individuals and small projects",
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
        "description": "For professionals and growing teams",
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
        "description": "For businesses with high-volume needs",
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

def create_stripe_products():
    """Create Stripe products for each pricing tier"""
    products = {}
    
    for tier, details in PRICING_TIERS.items():
        print(f"Creating product for {tier} tier...")
        
        # Create the product
        product = stripe.Product.create(
            name=details["name"],
            description=details["description"],
            metadata={
                "tier": tier,
                "features": json.dumps(details["features"]),
                "limits": json.dumps(details["limits"])
            }
        )
        
        # Create the price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=details["amount"],
            currency=details["currency"],
            recurring={"interval": "month"},
            metadata={"tier": tier}
        )
        
        products[tier] = {
            "product_id": product.id,
            "price_id": price.id
        }
        
        print(f"  Created product {product.id} with price {price.id}")
    
    return products

def list_stripe_products():
    """List existing Stripe products and prices"""
    products = stripe.Product.list(active=True, limit=100)
    
    print("\nExisting Products:")
    print("-----------------")
    
    for product in products:
        print(f"Product: {product.name} (ID: {product.id})")
        
        # Get prices for the product
        prices = stripe.Price.list(product=product.id, active=True)
        
        for price in prices:
            amount = price.unit_amount / 100  # Convert cents to dollars
            
            if price.type == "recurring":
                interval = price.recurring.interval
                print(f"  Price: ${amount:.2f}/{interval} (ID: {price.id})")
            else:
                print(f"  Price: ${amount:.2f} (one-time) (ID: {price.id})")
        
        print()  # Empty line for spacing

def write_env_file(products):
    """Write product and price IDs to .env file"""
    # Read existing .env file
    env_lines = []
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            env_lines = f.readlines()
    
    # Remove existing Stripe product/price variables
    env_lines = [line for line in env_lines if not line.startswith("STRIPE_BASIC_PRICE_ID=") and
                                              not line.startswith("STRIPE_PRO_PRICE_ID=") and
                                              not line.startswith("STRIPE_ENTERPRISE_PRICE_ID=")]
    
    # Add new variables
    env_lines.append(f"\n# Stripe price IDs (updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    env_lines.append(f"STRIPE_BASIC_PRICE_ID={products['basic']['price_id']}\n")
    env_lines.append(f"STRIPE_PRO_PRICE_ID={products['pro']['price_id']}\n")
    env_lines.append(f"STRIPE_ENTERPRISE_PRICE_ID={products['enterprise']['price_id']}\n")
    
    # Write back to .env file
    with open(".env", "w") as f:
        f.writelines(env_lines)
    
    print("\nUpdated .env file with price IDs")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Set up Stripe products and prices for DataForge")
    parser.add_argument("--list", action="store_true", help="List existing Stripe products and prices")
    parser.add_argument("--create", action="store_true", help="Create products and prices in Stripe")
    parser.add_argument("--update-env", action="store_true", help="Update .env file with price IDs")
    
    args = parser.parse_args()
    
    if args.list:
        list_stripe_products()
    
    if args.create:
        products = create_stripe_products()
        
        if args.update_env:
            write_env_file(products)
    
    if not args.list and not args.create:
        parser.print_help()

if __name__ == "__main__":
    main()