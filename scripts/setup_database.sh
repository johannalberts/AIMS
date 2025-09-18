#!/bin/bash
# AIMS Database Setup Script
# =========================
# This script initializes the MongoDB database with test lesson data

echo "🎯 AIMS Database Setup"
echo "======================"

# Wait for MongoDB to be ready
echo "⏳ Waiting for MongoDB to start..."
sleep 5

# Check if MongoDB is running
if ! docker ps | grep -q "aims_mongodb"; then
    echo "❌ MongoDB container not found. Please start with: docker-compose up -d mongodb"
    exit 1
fi

# Run the Python initialization script
echo "🚀 Running database initialization..."
uv run python fixtures/init_lesson_data.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database setup completed successfully!"
    echo "🎯 Your AIMS system is ready with Python OOP test lesson"
    echo ""
    echo "Next steps:"
    echo "1. Start the API: docker-compose up web"
    echo "2. Access docs: http://localhost:8000/docs"
    echo "3. Test the lesson data with AIMS graph"
else
    echo "❌ Database setup failed"
    exit 1
fi
