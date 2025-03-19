"""
app/scheduler.py - Scheduler for background tasks like subscription processing
"""
import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.db.config import SessionLocal
import app.db.crud as crud

logger = logging.getLogger(__name__)

# Create scheduler
scheduler = AsyncIOScheduler()

async def process_subscription_downgrades():
    """Process subscriptions with planned downgrades that have reached their end date"""
    db = SessionLocal()
    try:
        count = crud.process_planned_downgrades(db)
        if count > 0:
            logger.info(f"Processed {count} subscription downgrades")
    except Exception as e:
        logger.error(f"Error processing subscription downgrades: {str(e)}")
    finally:
        db.close()

async def clean_expired_checkout_sessions():
    """Clean up expired checkout sessions"""
    # This would require additional implementation in your db/crud.py file
    db = SessionLocal()
    try:
        # Example implementation:
        # count = crud.clean_expired_checkout_sessions(db)
        # if count > 0:
        #     logger.info(f"Cleaned {count} expired checkout sessions")
        pass
    except Exception as e:
        logger.error(f"Error cleaning expired checkout sessions: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    """Start the scheduler for background tasks"""
    # Schedule subscription downgrade processing
    scheduler.add_job(
        process_subscription_downgrades,
        IntervalTrigger(hours=1),  # Run every hour
        id='process_subscription_downgrades',
        replace_existing=True
    )
    
    # Schedule checkout session cleanup
    scheduler.add_job(
        clean_expired_checkout_sessions,
        IntervalTrigger(hours=6),  # Run every 6 hours
        id='clean_expired_checkout_sessions',
        replace_existing=True
    )
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started for subscription management tasks")

def shutdown_scheduler():
    """Shutdown the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler shutdown")