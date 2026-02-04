#!/usr/bin/env python3
"""
Test script for content management UI and API endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def login():
    """Login and get session cookie."""
    response = requests.post(
        f"{BASE_URL}/login",
        data={"email": "admin@aims.com", "password": "admin123"},
        allow_redirects=False
    )
    if 'aims_session' in response.cookies:
        return {'aims_session': response.cookies['aims_session']}
    return None

def test_api_endpoints(cookies):
    """Test all content management API endpoints."""
    print("\n=== Testing Content Management API ===\n")
    
    # 1. Test hierarchical data endpoint
    print("1. Testing GET /api/content-management/all")
    response = requests.get(f"{BASE_URL}/api/content-management/all", cookies=cookies)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success! Found {len(data['courses'])} course(s)")
        if data['courses']:
            course = data['courses'][0]
            print(f"   - Course: {course['title']}")
            print(f"   - Lessons: {len(course['lessons'])}")
            if course['lessons']:
                lesson = course['lessons'][0]
                print(f"   - First lesson: {lesson['title']}")
                print(f"   - Learning outcomes: {len(lesson['learning_outcomes'])}")
    else:
        print(f"   ✗ Failed with status {response.status_code}")
    
    # 2. Test manual content upload
    print("\n2. Testing POST /api/outcomes/1/content (manual upload)")
    response = requests.post(
        f"{BASE_URL}/api/outcomes/1/content",
        data={
            "content_text": "Test from script: A class is a code template for creating objects.",
            "content_type": "definition"
        },
        cookies=cookies
    )
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success! Created content chunk ID: {data['id']}")
        print(f"   - Status: {data['approval_status']}")
    else:
        print(f"   ✗ Failed with status {response.status_code}")
        print(f"   - Error: {response.text}")
    
    # 3. Test AI content generation
    print("\n3. Testing POST /api/outcomes/1/generate-content")
    response = requests.post(
        f"{BASE_URL}/api/outcomes/1/generate-content",
        cookies=cookies
    )
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success! Generated content:")
        if isinstance(data.get('generated_content'), dict):
            print(f"   - Sections: {', '.join(data['generated_content'].keys())}")
        else:
            print(f"   - Content preview: {str(data)[:100]}...")
    else:
        print(f"   ✗ Failed with status {response.status_code}")
    
    # 4. Test content listing for outcome
    print("\n4. Testing GET /api/outcomes/1/content")
    response = requests.get(f"{BASE_URL}/api/outcomes/1/content", cookies=cookies)
    if response.status_code == 200:
        data = response.json()
        chunks = data if isinstance(data, list) else data.get('content_chunks', [])
        print(f"   ✓ Success! Found {len(chunks)} content chunk(s)")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"   - Chunk {i}: {chunk['content_type']} ({chunk['source']}, {chunk['approval_status']})")
    else:
        print(f"   ✗ Failed with status {response.status_code}")
    
    # 5. Test content update
    print("\n5. Testing PUT /api/content/1")
    response = requests.put(
        f"{BASE_URL}/api/content/1",
        json={
            "content_text": "Updated: A class in Python is defined using the 'class' keyword followed by the class name.",
            "approval_status": "approved"
        },
        cookies=cookies
    )
    if response.status_code == 200:
        print(f"   ✓ Success! Content updated")
    else:
        print(f"   ✗ Failed with status {response.status_code}")
        print(f"   - Error: {response.text}")
    
    # 6. Test similarity search
    print("\n6. Testing GET /api/outcomes/1/similar-content")
    response = requests.get(
        f"{BASE_URL}/api/outcomes/1/similar-content?query=class definition python",
        cookies=cookies
    )
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success! Found {len(data)} similar content chunk(s)")
    else:
        print(f"   ✗ Failed with status {response.status_code}")

def test_page_access(cookies):
    """Test content management page loads."""
    print("\n=== Testing Page Access ===\n")
    
    response = requests.get(f"{BASE_URL}/admin/content-management", cookies=cookies)
    if response.status_code == 200:
        print("✓ Content management page loads successfully")
        if "Learning Content Management" in response.text:
            print("✓ Page title found")
        if "accordion" in response.text.lower():
            print("✓ Accordion UI detected")
        if "uploadModal" in response.text:
            print("✓ Upload modal found")
    else:
        print(f"✗ Page failed to load: {response.status_code}")

def main():
    print("=" * 60)
    print("AIMS Content Management Testing")
    print("=" * 60)
    
    # Login
    print("\nLogging in as admin...")
    cookies = login()
    if not cookies:
        print("✗ Login failed!")
        return
    print("✓ Login successful")
    
    # Run tests
    test_page_access(cookies)
    test_api_endpoints(cookies)
    
    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
