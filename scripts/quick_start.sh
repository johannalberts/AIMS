#!/bin/bash
# AIMS Quick Start Script

echo "================================="
echo "🎯 AIMS Quick Start"
echo "================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your OPENAI_API_KEY"
    echo "   Then run this script again."
    exit 1
fi

# Check if OPENAI_API_KEY is set
if grep -q "your-openai-api-key-here" .env; then
    echo "⚠️  Please set your OPENAI_API_KEY in .env file"
    exit 1
fi

echo "🐘 Starting PostgreSQL..."
docker compose up -d postgres

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

echo "📊 Initializing database..."
uv run python scripts/init_database.py

echo ""
echo "================================="
echo "✅ Setup Complete!"
echo "================================="
echo ""
echo "🚀 Start the application with:"
echo "   uv run uvicorn app.main:app --reload"
echo ""
echo "🌐 Then visit:"
echo "   http://localhost:8000"
echo ""
echo "🔑 Login as:"
echo "   Admin: admin@aims.com / admin123"
echo "   Learner: learner@aims.com / learner123"
echo ""
echo "================================="
