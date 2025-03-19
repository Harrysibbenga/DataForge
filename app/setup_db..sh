#!/bin/bash
# setup_db.sh - Set up the database and create initial migration

# Create migrations directory structure
mkdir -p migrations/versions

# Copy alembic files
cp alembic.ini .
mkdir -p migrations
cp migrations/env.py migrations/
cp migrations/script.py.mako migrations/

# Create initial migration
echo "Creating initial migration..."
alembic revision --autogenerate -m "Initial migration"

# Run migration
echo "Running migration..."
alembic upgrade head

echo "Database setup complete!"
