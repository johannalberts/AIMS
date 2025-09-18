#!/usr/bin/env python3
"""
AIMS MongoDB Initialization Script
==================================
This script initializes the MongoDB database with test lesson data.
Run this after starting MongoDB to populate the database.

Usage:
    python fixtures/init_lesson_data.py
"""

import os
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "aims_db"

def get_database():
    """Get MongoDB database connection."""
    client = MongoClient(MONGODB_URL)
    return client[DATABASE_NAME]

def create_python_oop_lesson():
    """Create the Python OOP lesson data structure."""
    return {
        "_id": ObjectId("64f1a2b3c4d5e6f789012345"),
        "title": "Python Object-Oriented Programming Fundamentals",
        "subject": "Computer Science",
        "topic": "Python OOP",
        "description": "Master the fundamentals of object-oriented programming in Python, including classes, objects, inheritance, and polymorphism.",
        "difficulty_level": "intermediate",
        "estimated_duration_minutes": 120,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        
        # Learning outcomes compatible with AIMS graph structure
        "learning_outcomes": {
            "class_definition": {
                "description": "Understanding how to define and structure classes in Python with proper syntax and conventions",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "Class keyword and naming conventions",
                        "Instance variables and class variables",
                        "Constructor method (__init__)",
                        "Instance methods vs class methods vs static methods"
                    ],
                    "examples": [
                        "class Student:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n\n    def introduce(self):\n        return f'Hi, I am {self.name} and I am {self.age} years old'"
                    ]
                }
            },
            
            "object_instantiation": {
                "description": "Understanding how to create and use objects (instances) from classes",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "Creating instances from classes",
                        "Accessing instance attributes and methods",
                        "Object identity and state",
                        "Multiple instances and their independence"
                    ],
                    "examples": [
                        "student1 = Student('Alice', 20)\nstudent2 = Student('Bob', 22)\nprint(student1.introduce())\nprint(student2.name)"
                    ]
                }
            },
            
            "inheritance_concepts": {
                "description": "Understanding inheritance principles including parent-child relationships and method overriding",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "Parent class (superclass) and child class (subclass)",
                        "Method inheritance and overriding",
                        "super() function usage",
                        "Multiple inheritance basics"
                    ],
                    "examples": [
                        "class Animal:\n    def speak(self):\n        pass\n\nclass Dog(Animal):\n    def speak(self):\n        return 'Woof!'\n\nclass Cat(Animal):\n    def speak(self):\n        return 'Meow!'"
                    ]
                }
            },
            
            "encapsulation_principles": {
                "description": "Understanding data encapsulation, private/protected attributes, and access control in Python",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "Public, protected, and private attributes",
                        "Name mangling with double underscore",
                        "Getter and setter methods",
                        "Property decorators"
                    ],
                    "examples": [
                        "class BankAccount:\n    def __init__(self, balance):\n        self.__balance = balance  # Private attribute\n    \n    @property\n    def balance(self):\n        return self.__balance\n    \n    def deposit(self, amount):\n        if amount > 0:\n            self.__balance += amount"
                    ]
                }
            },
            
            "polymorphism_application": {
                "description": "Understanding and implementing polymorphism through method overriding and duck typing",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "Method overriding in inheritance",
                        "Duck typing principles",
                        "Abstract base classes",
                        "Interface-like behavior"
                    ],
                    "examples": [
                        "def make_sound(animal):\n    return animal.speak()  # Polymorphic behavior\n\ndog = Dog()\ncat = Cat()\nprint(make_sound(dog))  # Woof!\nprint(make_sound(cat))  # Meow!"
                    ]
                }
            },
            
            "special_methods": {
                "description": "Understanding and implementing Python's special methods (magic methods) for operator overloading",
                "mastery_level": 0.0,
                "content": {
                    "key_concepts": [
                        "__str__ and __repr__ methods",
                        "__eq__, __lt__, and comparison methods",
                        "__add__, __sub__, and arithmetic methods",
                        "__len__, __getitem__ for container-like behavior"
                    ],
                    "examples": [
                        "class Vector:\n    def __init__(self, x, y):\n        self.x = x\n        self.y = y\n    \n    def __add__(self, other):\n        return Vector(self.x + other.x, self.y + other.y)\n    \n    def __str__(self):\n        return f'Vector({self.x}, {self.y})'"
                    ]
                }
            }
        },
        
        # Additional lesson metadata
        "prerequisites": ["Python basics", "Functions", "Variables and data types"],
        "tags": ["python", "oop", "programming", "classes", "objects"],
        
        # Assessment configuration
        "assessment_config": {
            "mastery_threshold": 0.8,
            "max_attempts_per_outcome": 3,
            "reteach_threshold": 2,
            "passing_score": 0.75
        }
    }

def create_sample_assessment_session(lesson_id):
    """Create a sample assessment session for testing."""
    return {
        "_id": ObjectId("64f1a2b3c4d5e6f789012346"),
        "lesson_id": lesson_id,
        "student_id": "test_student_001",
        "status": "in_progress",
        "current_outcome_key": "",
        "session_state": {
            "topic": "Python OOP",
            "learning_outcomes": {
                "class_definition": {
                    "description": "Understanding how to define and structure classes in Python with proper syntax and conventions",
                    "mastery_level": 0.0
                },
                "object_instantiation": {
                    "description": "Understanding how to create and use objects (instances) from classes",
                    "mastery_level": 0.0
                },
                "inheritance_concepts": {
                    "description": "Understanding inheritance principles including parent-child relationships and method overriding",
                    "mastery_level": 0.0
                },
                "encapsulation_principles": {
                    "description": "Understanding data encapsulation, private/protected attributes, and access control in Python",
                    "mastery_level": 0.0
                },
                "polymorphism_application": {
                    "description": "Understanding and implementing polymorphism through method overriding and duck typing",
                    "mastery_level": 0.0
                },
                "special_methods": {
                    "description": "Understanding and implementing Python's special methods (magic methods) for operator overloading",
                    "mastery_level": 0.0
                }
            },
            "current_outcome_key": "",
            "last_question": "",
            "last_response": "",
            "failed_attempts": 0,
            "feedback": ""
        },
        "progress": {
            "total_outcomes": 6,
            "mastered_outcomes": 0,
            "current_outcome_index": 0,
            "overall_progress_percentage": 0.0
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

def init_database():
    """Initialize the AIMS database with test data."""
    print("🔗 Connecting to MongoDB...")
    
    try:
        db = get_database()
        
        # Test connection
        db.list_collection_names()
        print("✅ Connected to MongoDB successfully")
        
        # Create collections
        print("📁 Creating collections...")
        if "lessons" not in db.list_collection_names():
            db.create_collection("lessons")
        if "assessment_sessions" not in db.list_collection_names():
            db.create_collection("assessment_sessions")
        
        # Insert lesson data
        print("📚 Inserting Python OOP lesson...")
        lesson_data = create_python_oop_lesson()
        
        # Check if lesson already exists
        existing_lesson = db.lessons.find_one({"_id": lesson_data["_id"]})
        if existing_lesson:
            print("⚠️  Lesson already exists, updating...")
            db.lessons.replace_one({"_id": lesson_data["_id"]}, lesson_data)
        else:
            db.lessons.insert_one(lesson_data)
        
        print("✅ Lesson inserted successfully")
        
        # Insert sample assessment session
        print("🧪 Creating sample assessment session...")
        session_data = create_sample_assessment_session(lesson_data["_id"])
        
        # Check if session already exists
        existing_session = db.assessment_sessions.find_one({"_id": session_data["_id"]})
        if existing_session:
            print("⚠️  Assessment session already exists, updating...")
            db.assessment_sessions.replace_one({"_id": session_data["_id"]}, session_data)
        else:
            db.assessment_sessions.insert_one(session_data)
        
        print("✅ Sample assessment session created")
        
        # Summary
        total_lessons = db.lessons.count_documents({})
        total_sessions = db.assessment_sessions.count_documents({})
        
        print("\n🎉 Database initialization completed!")
        print(f"📚 Total lessons: {total_lessons}")
        print(f"🧪 Total assessment sessions: {total_sessions}")
        print(f"🎯 Learning outcomes: 6 (class definition, object instantiation, inheritance, encapsulation, polymorphism, special methods)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

def extract_aims_compatible_data(lesson_id=None):
    """Extract lesson data in AIMS-compatible format."""
    try:
        db = get_database()
        
        # Get lesson
        if lesson_id:
            lesson = db.lessons.find_one({"_id": ObjectId(lesson_id)})
        else:
            lesson = db.lessons.find_one({"topic": "Python OOP"})
        
        if not lesson:
            print("❌ No lesson found")
            return None
        
        # Extract AIMS-compatible format
        aims_data = {
            "topic": lesson["topic"],
            "learning_outcomes": lesson["learning_outcomes"]
        }
        
        print("✅ AIMS-compatible data extracted:")
        print(f"📚 Topic: {aims_data['topic']}")
        print(f"🎯 Learning outcomes: {len(aims_data['learning_outcomes'])}")
        
        return aims_data
        
    except Exception as e:
        print(f"❌ Error extracting data: {e}")
        return None

if __name__ == "__main__":
    print("🎯 AIMS Database Initialization")
    print("=" * 50)
    
    # Initialize database
    success = init_database()
    
    if success:
        print("\n📤 Testing AIMS data extraction...")
        aims_data = extract_aims_compatible_data()
        
        if aims_data:
            print("\n💡 Usage in AIMS graph:")
            print("```python")
            print("from app.services.graph import AIMSGraph")
            print("")
            print("# Extract lesson from database")
            print("lesson_data = extract_aims_compatible_data()")
            print("")
            print("# Create initial state")
            print("initial_state = AIMSGraph.create_initial_state(")
            print(f"    topic='{aims_data['topic']}',")
            print("    learning_outcomes=lesson_data['learning_outcomes']")
            print(")")
            print("")
            print("# Start assessment")
            print("graph = AIMSGraph()")
            print("result = graph.invoke(initial_state)")
            print("```")
    
    else:
        print("❌ Database initialization failed")
        exit(1)
