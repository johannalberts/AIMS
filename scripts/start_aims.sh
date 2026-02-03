#!/bin/bash
# AIMS Quick Start Script
# =======================
# This script starts all necessary services for AIMS

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the project root (parent of scripts directory)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

echo "🎯 AIMS Quick Start"
echo "==================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Please create it from the example:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env and add your OPENAI_API_KEY"
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Start MongoDB
echo ""
echo "📦 Starting MongoDB..."
docker compose up -d mongodb

# Wait for MongoDB to be ready
echo "⏳ Waiting for MongoDB to initialize..."
sleep 5

# Check if MongoDB is running
if ! docker ps | grep -q "aims_mongodb"; then
    echo "❌ MongoDB failed to start"
    exit 1
fi
echo "✅ MongoDB is running"

# Initialize database
echo ""
echo "💾 Initializing database with test lesson..."
uv run python fixtures/init_lesson_data.py

if [ $? -ne 0 ]; then
    echo "❌ Database initialization failed"
    exit 1
fi

# Verify setup
echo ""
echo "🔍 Verifying setup..."
uv run python scripts/verify_frontend_setup.py

# Start the application
echo ""
echo "🚀 Starting AIMS application..."
echo "================================"
echo "Backend + Frontend will start now"
echo "Press Ctrl+C to stop"
echo ""
echo "📱 Access AIMS at: http://localhost:8000"
echo "📚 API docs at: http://localhost:8000/docs"
echo ""
echo "Starting server..."
echo "================================"
echo ""

uv run uvicorn app.main:app --reload