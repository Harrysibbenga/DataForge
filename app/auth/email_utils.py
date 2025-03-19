"""
app/auth/email_utils.py - Utilities for email verification and notifications
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import secrets
import jwt
from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Setup logging
logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@dataforge.com")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "DataForge")

# JWT configuration for email tokens
EMAIL_TOKEN_SECRET = os.environ.get("EMAIL_TOKEN_SECRET", os.environ.get("JWT_SECRET_KEY", "email_verification_secret"))
EMAIL_TOKEN_ALGORITHM = "HS256"
EMAIL_TOKEN_EXPIRE_HOURS = 24

# Set up Jinja2 template environment
template_env = Environment(
    loader=FileSystemLoader("app/templates/emails"),
    autoescape=select_autoescape(['html', 'xml'])
)

def generate_verification_token(email: str) -> str:
    """Generate a verification token for email verification"""
    expiration = datetime.utcnow() + timedelta(hours=EMAIL_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": email,
        "exp": expiration,
        "type": "email_verification",
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, EMAIL_TOKEN_SECRET, algorithm=EMAIL_TOKEN_ALGORITHM)

def verify_email_token(token: str) -> str:
    """Verify an email verification token and return the email"""
    try:
        payload = jwt.decode(token, EMAIL_TOKEN_SECRET, algorithms=[EMAIL_TOKEN_ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if email is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
        
        if token_type != "email_verification":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
            
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

def generate_password_reset_token(email: str) -> str:
    """Generate a token for password reset"""
    expiration = datetime.utcnow() + timedelta(hours=1)  # Shorter expiration for security
    payload = {
        "sub": email,
        "exp": expiration,
        "type": "password_reset",
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, EMAIL_TOKEN_SECRET, algorithm=EMAIL_TOKEN_ALGORITHM)

def verify_password_reset_token(token: str) -> str:
    """Verify a password reset token and return the email"""
    try:
        payload = jwt.decode(token, EMAIL_TOKEN_SECRET, algorithms=[EMAIL_TOKEN_ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        
        if email is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
        
        if token_type != "password_reset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
            
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

def send_email(recipient: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """Send an email using SMTP"""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured, email not sent")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
        message["To"] = recipient
        
        # Add text part if provided, otherwise create a simple version from HTML
        if text_content is None:
            # Very simple conversion - in production you'd want better HTML to text conversion
            text_content = html_content.replace('<br>', '\n').replace('</p>', '\n\n')
            text_content = ''.join(c for c in text_content if ord(c) < 128)  # Remove non-ASCII
        
        # Attach parts
        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))
        
        # Connect to server and send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, recipient, message.as_string())
        
        logger.info(f"Email sent successfully to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_verification_email(email: str, token: str, base_url: str) -> bool:
    """Send verification email to user"""
    verification_url = f"{base_url}/verify-email?token={token}"
    
    # Get email template
    template = template_env.get_template("email_verification.html")
    html_content = template.render(
        verification_url=verification_url,
        support_email="support@dataforge.com",
        hours=EMAIL_TOKEN_EXPIRE_HOURS
    )
    
    # Send email
    return send_email(
        recipient=email,
        subject="Verify your DataForge account",
        html_content=html_content
    )

def send_password_reset_email(email: str, token: str, base_url: str) -> bool:
    """Send password reset email to user"""
    reset_url = f"{base_url}/reset-password?token={token}"
    
    # Get email template
    template = template_env.get_template("password_reset.html")
    html_content = template.render(
        reset_url=reset_url,
        support_email="support@dataforge.com",
        hours=1  # Password reset links expire after 1 hour
    )
    
    # Send email
    return send_email(
        recipient=email,
        subject="Reset your DataForge password",
        html_content=html_content
    )

def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email to verified user"""
    # Get email template
    template = template_env.get_template("welcome.html")
    html_content = template.render(
        name=name,
        support_email="support@dataforge.com"
    )
    
    # Send email
    return send_email(
        recipient=email,
        subject="Welcome to DataForge!",
        html_content=html_content
    )