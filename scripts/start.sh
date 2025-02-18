#!/bin/bash

# Add app directory to Python path
export PYTHONPATH=$PYTHONPATH:/app

# Run migrations
alembic upgrade head

# Start the application
exec "$@" 