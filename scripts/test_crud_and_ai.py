"""
Test script for CRUD operations and AI lesson suggestions.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def login():
    """Login as content manager"""
    response = requests.post(
        f"{BASE_URL}/login",
        data={
            "email": "content_mgr@aims.com",
            "password": "content123"
        },
        allow_redirects=False
    )
    
    # Extract session cookie
    cookies = response.cookies
    return cookies

def test_course_crud(cookies):
    """Test course CRUD operations"""
    print("\n=== Testing Course CRUD ===")
    
    # Create course
    print("Creating new course...")
    response = requests.post(
        f"{BASE_URL}/api/courses",
        data={
            "title": "Advanced Python Programming",
            "subject": "Programming",
            "description": "Master advanced Python concepts",
            "difficulty_level": "advanced"
        },
        cookies=cookies
    )
    
    if response.status_code == 200:
        course = response.json()
        print(f"✓ Course created: {course['title']} (ID: {course['id']})")
        
        # Update course
        print("Updating course...")
        response = requests.put(
            f"{BASE_URL}/api/courses/{course['id']}",
            data={
                "title": "Advanced Python Programming - Updated",
                "subject": "Programming",
                "description": "Master advanced Python concepts and patterns",
                "difficulty_level": "advanced"
            },
            cookies=cookies
        )
        
        if response.status_code == 200:
            updated = response.json()
            print(f"✓ Course updated: {updated['title']}")
        
        return course['id']
    else:
        print(f"✗ Failed to create course: {response.text}")
        return None

def test_ai_lesson_suggestion(cookies, course_id):
    """Test AI lesson structure suggestion"""
    print("\n=== Testing AI Lesson Suggestion ===")
    
    print("Requesting AI suggestion...")
    response = requests.post(
        f"{BASE_URL}/api/lessons/suggest-structure",
        json={
            "lesson_title": "Decorators and Metaclasses",
            "lesson_topic": "Advanced Python Features",
            "lesson_description": "Understanding and implementing decorators and metaclasses",
            "course_id": course_id
        },
        cookies=cookies
    )
    
    if response.status_code == 200:
        suggestion = response.json()
        print(f"✓ AI Suggestion received:")
        print(f"  Overview: {suggestion['suggestion']['lesson_overview'][:100]}...")
        print(f"  Duration: {suggestion['suggestion']['estimated_duration_minutes']} minutes")
        print(f"  Learning Outcomes: {len(suggestion['suggestion']['learning_outcomes'])}")
        
        for i, lo in enumerate(suggestion['suggestion']['learning_outcomes'], 1):
            print(f"    {i}. {lo['key']}: {lo['description'][:60]}...")
        
        # Create lesson from AI suggestion
        print("\nCreating lesson from AI suggestion...")
        response = requests.post(
            f"{BASE_URL}/api/lessons/create-from-suggestion",
            json={
                "course_id": course_id,
                "lesson_title": "Decorators and Metaclasses",
                "lesson_topic": "Advanced Python Features",
                "lesson_description": "Understanding and implementing decorators and metaclasses",
                "lesson_overview": suggestion['suggestion']['lesson_overview'],
                "estimated_duration_minutes": suggestion['suggestion']['estimated_duration_minutes'],
                "learning_outcomes": suggestion['suggestion']['learning_outcomes']
            },
            cookies=cookies
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Lesson created with {len(result['learning_outcomes'])} learning outcomes")
            return result['lesson']['id']
        else:
            print(f"✗ Failed to create lesson: {response.text}")
    else:
        print(f"✗ Failed to get AI suggestion: {response.text}")
    
    return None

def test_manual_lesson_crud(cookies, course_id):
    """Test manual lesson CRUD operations"""
    print("\n=== Testing Manual Lesson CRUD ===")
    
    print("Creating manual lesson...")
    response = requests.post(
        f"{BASE_URL}/api/courses/{course_id}/lessons",
        data={
            "title": "Context Managers",
            "topic": "Python Context Managers",
            "description": "Understanding and creating context managers",
            "estimated_duration_minutes": 45,
            "mastery_threshold": 0.85
        },
        cookies=cookies
    )
    
    if response.status_code == 200:
        lesson = response.json()
        print(f"✓ Lesson created: {lesson['title']} (ID: {lesson['id']})")
        return lesson['id']
    else:
        print(f"✗ Failed to create lesson: {response.text}")
        return None

def test_outcome_crud(cookies, lesson_id):
    """Test learning outcome CRUD operations"""
    print("\n=== Testing Learning Outcome CRUD ===")
    
    print("Creating learning outcome...")
    response = requests.post(
        f"{BASE_URL}/api/lessons/{lesson_id}/outcomes",
        data={
            "key": "with_statement",
            "description": "Understand and use the with statement for resource management",
            "key_concepts": "Context managers, __enter__, __exit__, resource cleanup",
            "examples": "File handling, database connections, locks"
        },
        cookies=cookies
    )
    
    if response.status_code == 200:
        outcome = response.json()
        print(f"✓ Learning outcome created: {outcome['key']}")
        
        # Update outcome
        print("Updating learning outcome...")
        response = requests.put(
            f"{BASE_URL}/api/outcomes/{outcome['id']}",
            data={
                "key": "with_statement_advanced",
                "description": "Master the with statement and create custom context managers",
                "key_concepts": "Context managers, __enter__, __exit__, contextlib, resource cleanup",
                "examples": "File handling, database connections, locks, custom contexts"
            },
            cookies=cookies
        )
        
        if response.status_code == 200:
            updated = response.json()
            print(f"✓ Learning outcome updated: {updated['key']}")
        
        return outcome['id']
    else:
        print(f"✗ Failed to create outcome: {response.text}")
        return None

def test_content_management_page(cookies):
    """Test that the content management page loads"""
    print("\n=== Testing Content Management Page ===")
    
    response = requests.get(
        f"{BASE_URL}/content-management",
        cookies=cookies
    )
    
    if response.status_code == 200:
        print("✓ Content management page loaded successfully")
        
        # Test API endpoint
        response = requests.get(
            f"{BASE_URL}/api/content-management/all",
            cookies=cookies
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API returned {len(data['courses'])} courses")
            for course in data['courses']:
                print(f"  - {course['title']}: {len(course['lessons'])} lessons")
        else:
            print(f"✗ API call failed: {response.text}")
    else:
        print(f"✗ Page load failed: {response.status_code}")

def main():
    """Run all tests"""
    print("=" * 60)
    print("AIMS Content Management CRUD & AI Tests")
    print("=" * 60)
    
    # Login
    print("\nLogging in as content manager...")
    cookies = login()
    print("✓ Logged in successfully")
    
    # Test course CRUD
    course_id = test_course_crud(cookies)
    
    if course_id:
        # Test AI lesson suggestion
        test_ai_lesson_suggestion(cookies, course_id)
        
        # Test manual lesson creation
        lesson_id = test_manual_lesson_crud(cookies, course_id)
        
        if lesson_id:
            # Test outcome CRUD
            test_outcome_crud(cookies, lesson_id)
    
    # Test content management page
    test_content_management_page(cookies)
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
