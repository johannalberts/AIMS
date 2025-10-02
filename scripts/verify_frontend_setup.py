#!/usr/bin/env python3
"""
Quick test script to verify AIMS frontend setup
"""

import os
import sys
from pathlib import Path

def check_file(path, description):
    """Check if a file exists."""
    if Path(path).exists():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {path}")
        return False

def check_directory(path, description):
    """Check if a directory exists."""
    if Path(path).is_dir():
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description} NOT FOUND: {path}")
        return False

def main():
    print("🔍 AIMS Frontend Setup Verification")
    print("=" * 50)
    
    # Get the project root (parent of scripts directory if running from scripts/)
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "scripts":
        project_root = script_path.parent.parent
        os.chdir(project_root)
        print(f"📂 Working from project root: {project_root}\n")
    
    all_good = True
    
    # Check static directory
    print("\n📁 Checking static files...")
    all_good &= check_directory("static", "Static directory")
    all_good &= check_file("static/index.html", "HTML file")
    all_good &= check_file("static/style.css", "CSS file")
    all_good &= check_file("static/app.js", "JavaScript file")
    all_good &= check_file("static/SETUP.md", "Setup guide")
    
    # Check backend files
    print("\n🐍 Checking backend files...")
    all_good &= check_file("app/main.py", "FastAPI main")
    all_good &= check_file("app/services/graph.py", "AIMS graph")
    
    # Check fixtures
    print("\n🧪 Checking test data...")
    all_good &= check_directory("fixtures", "Fixtures directory")
    all_good &= check_file("fixtures/init_lesson_data.py", "Data initialization script")
    
    # Check environment
    print("\n🔐 Checking environment...")
    if Path(".env").exists():
        print("✅ .env file found")
        # Try to load it to check if OPENAI_API_KEY is present
        try:
            with open(".env", "r") as f:
                env_content = f.read()
                if "OPENAI_API_KEY" in env_content and not env_content.startswith("#OPENAI_API_KEY"):
                    print("✅ OPENAI_API_KEY configured in .env")
                else:
                    print("⚠️  OPENAI_API_KEY not configured in .env file")
                    print("   Edit .env and add: OPENAI_API_KEY=your-key-here")
                    all_good = False
        except Exception as e:
            print(f"⚠️  Could not read .env file: {e}")
    else:
        print("⚠️  .env file not found")
        print("   Create it with: cp .env.example .env")
        print("   Then add your OPENAI_API_KEY")
        all_good = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_good:
        print("✅ All checks passed!")
        print("\n🚀 Ready to start AIMS:")
        print("   1. docker compose up -d mongodb")
        print("   2. uv run python fixtures/init_lesson_data.py")
        print("   3. uv run uvicorn app.main:app --reload")
        print("   4. Open http://localhost:8000")
        return 0
    else:
        print("❌ Some checks failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())