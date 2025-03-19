# DataForge Deployment Guide

This guide walks you through deploying the DataForge application to Heroku and setting up Stripe for payments.

## Prerequisites

* [Heroku Account](https://signup.heroku.com/) (Free tier works for initial setup)
* [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
* [Stripe Account](https://dashboard.stripe.com/register) (Free to sign up)
* Git installed
* Your DataForge codebase ready

## Step 1: Prepare Your Application for Heroku

First, make sure you have the necessary files for Heroku deployment:

### 1. Create a Procfile

Create a file named `Procfile` (no extension) in your project root:

```
web: uvicorn main:app --host=0.0.0.0 --port=${PORT:-8000}
```

### 2. Create a runtime.txt file

Specify the Python version:

```
python-3.9.18
```

### 3. Update your requirements.txt

Make sure your `requirements.txt` includes all dependencies including Stripe:

```bash
fastapi==0.103.1
uvicorn==0.23.2
pydantic==2.0.3  # Using 2.0.3 instead of 2.3.0 for compatibility
python-multipart==0.0.6
jinja2==3.1.2
pandas==2.0.3  # Using 2.0.3 instead of 2.1.0 for compatibility
openpyxl==3.1.2
lxml==4.9.3
pyyaml==6.0.1
stripe==5.4.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

## Step 2: Set Up Stripe

### 1. Create Products and Prices in Stripe Dashboard

1. Log in to your [Stripe Dashboard](https://dashboard.stripe.com/)
2. Go to Products → Create Product
3. Create three subscription products:
   * Basic Plan ($9.99/month)
   * Pro Plan ($24.99/month) 
   * Enterprise Plan ($99.99/month)
4. For each product, create a recurring price (monthly billing)
5. Take note of the price IDs (they look like `price_1234567890`)

### 2. Set up Webhook Endpoint

1. In the Stripe Dashboard, go to Developers → Webhooks
2. Add an endpoint (you'll update the URL after deploying to Heroku)
3. Select events to listen for:
   * `customer.subscription.created`
   * `customer.subscription.updated`
   * `customer.subscription.deleted`
   * `invoice.paid`
   * `invoice.payment_failed`
4. Take note of the Webhook Signing Secret

## Step 3: Initialize Git Repository (if not already)

```bash
git init
git add .
git commit -m "Initial commit for Heroku deployment"
```

## Step 4: Create and Configure Heroku App

```bash
# Login to Heroku
heroku login

# Create a new Heroku app
heroku create dataforge-app

# Add Heroku remote
git remote add heroku https://git.heroku.com/dataforge-app.git
```

## Step 5: Configure Environment Variables

Set up the necessary environment variables in Heroku:

```bash
heroku config:set STRIPE_SECRET_KEY=sk_test_your_secret_key
heroku config:set STRIPE_BASIC_PRICE_ID=price_your_basic_price_id
heroku config:set STRIPE_PRO_PRICE_ID=price_your_pro_price_id
heroku config:set STRIPE_ENTERPRISE_PRICE_ID=price_your_enterprise_price_id
heroku config:set STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
heroku config:set JWT_SECRET_KEY=your_secret_key_for_jwt
```

Replace the placeholder values with your actual Stripe keys and IDs.

## Step 6: Deploy to Heroku

Push your code to Heroku:

```bash
git push heroku main
```

If you're working from a different branch, use:

```bash
git push heroku your-branch:main
```

## Step 7: Update Stripe Webhook URL

Now that your app is deployed, update your webhook endpoint URL in the Stripe Dashboard:

```
https://dataforge-app.herokuapp.com/api/payment/webhook
```

## Step 8: Open and Test Your Application

```bash
heroku open
```

This will open your deployed application in a browser.

## Step 9: Set Up a Custom Domain (Optional)

To use a custom domain (like dataforge.io):

```bash
heroku domains:add www.dataforge.io
heroku domains:add dataforge.io
```

Follow the instructions provided by Heroku to configure your DNS settings.

## Step 10: Monitoring and Scaling

* Monitor your application using the Heroku Dashboard
* View logs with `heroku logs --tail`
* Scale dynos as needed with `heroku ps:scale web=1`

## Troubleshooting

### Application Error on Heroku

Check the logs:

```bash
heroku logs --tail
```

### Stripe Webhook Not Working

1. Verify the webhook URL is correct
2. Check that the webhook signing secret is set correctly
3. Review Stripe Dashboard webhook logs for failed attempts

### Database Issues

For persistence beyond Heroku's ephemeral filesystem, add a database:

```bash
heroku addons:create heroku-postgresql:hobby-dev
```

You'll need to modify your application to use the database URL from the `DATABASE_URL` environment variable.

## Next Steps

1. Implement a real database (PostgreSQL)
2. Set up Continuous Integration/Deployment
3. Add monitoring and alerting
4. Implement analytics to track usage

