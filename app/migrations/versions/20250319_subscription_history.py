"""
app/migrations/versions/20250319_subscription_history.py
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '01f2a54d6e12'
down_revision = None  # Update this with your last migration if you have one
branch_labels = None
depends_on = None


def upgrade():
    # Create subscription history table
    op.create_table(
        'subscription_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('subscription_id', sa.String(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=False),
        sa.Column('previous_plan', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),  # created, updated, cancelled, etc.
        sa.Column('action_date', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add planned_downgrade_to column to subscriptions table
    op.add_column('subscriptions', sa.Column('planned_downgrade_to', sa.String(), nullable=True))
    
    # Add stripe_checkout_session_id column to subscriptions table
    op.add_column('subscriptions', sa.Column('stripe_checkout_session_id', sa.String(), nullable=True))
    
    # Indexes for performance
    op.create_index(op.f('ix_subscription_history_user_id'), 'subscription_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscription_history_subscription_id'), 'subscription_history', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_subscription_history_stripe_subscription_id'), 'subscription_history', ['stripe_subscription_id'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_subscription_history_stripe_subscription_id'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_subscription_id'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_user_id'), table_name='subscription_history')
    
    # Drop new columns from subscriptions
    op.drop_column('subscriptions', 'stripe_checkout_session_id')
    op.drop_column('subscriptions', 'planned_downgrade_to')
    
    # Drop the subscription history table
    op.drop_table('subscription_history')
