// MongoDB initialization script for AIMS test data
// This script runs automatically when the MongoDB container starts

// Switch to the aims_db database
db = db.getSiblingDB('aims_db');

// Create collections
db.createCollection('lessons');
db.createCollection('assessment_sessions');

// Insert test lesson: Python Object-Oriented Programming
db.lessons.insertOne({
  _id: ObjectId("64f1a2b3c4d5e6f789012345"),
  title: "Python Object-Oriented Programming Fundamentals",
  subject: "Computer Science",
  topic: "Python OOP",
  description: "Master the fundamentals of object-oriented programming in Python, including classes, objects, inheritance, and polymorphism.",
  difficulty_level: "intermediate",
  estimated_duration_minutes: 120,
  created_at: new Date(),
  updated_at: new Date(),
  
  // Learning outcomes compatible with AIMS graph structure
  learning_outcomes: {
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
  
  // Additional lesson metadata
  prerequisites: ["Python basics", "Functions", "Variables and data types"],
  tags: ["python", "oop", "programming", "classes", "objects"],
  
  // Assessment configuration
  assessment_config: {
    "mastery_threshold": 0.8,
    "max_attempts_per_outcome": 3,
    "reteach_threshold": 2,
    "passing_score": 0.75
  }
});

// Insert a sample assessment session for testing
db.assessment_sessions.insertOne({
  _id: ObjectId("64f1a2b3c4d5e6f789012346"),
  lesson_id: ObjectId("64f1a2b3c4d5e6f789012345"),
  student_id: "test_student_001",
  status: "in_progress",
  current_outcome_key: "",
  session_state: {
    topic: "Python OOP",
    learning_outcomes: {
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
    current_outcome_key: "",
    last_question: "",
    last_response: "",
    failed_attempts: 0,
    feedback: ""
  },
  progress: {
    total_outcomes: 6,
    mastered_outcomes: 0,
    current_outcome_index: 0,
    overall_progress_percentage: 0.0
  },
  created_at: new Date(),
  updated_at: new Date()
});

print("✅ AIMS test lesson and sample data loaded successfully!");
print("📚 Lesson: Python Object-Oriented Programming Fundamentals");
print("🎯 Learning Outcomes: 6 outcomes covering classes, objects, inheritance, encapsulation, polymorphism, and special methods");
print("🧪 Sample assessment session created for testing");
