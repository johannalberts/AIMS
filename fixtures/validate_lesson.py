#!/usr/bin/env python3
"""
Test script to validate the Python OOP lesson structure with AIMS graph.
Run this to verify the lesson data is compatible with the AIMS system.
"""

# Test lesson structure compatible with AIMS
python_oop_lesson = {
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
    }
}

def validate_lesson_structure():
    """Validate that the lesson structure matches AIMS requirements."""
    print("🧪 Validating Python OOP lesson structure for AIMS compatibility...")
    
    # Check required fields
    assert "topic" in python_oop_lesson, "Missing 'topic' field"
    assert "learning_outcomes" in python_oop_lesson, "Missing 'learning_outcomes' field"
    
    outcomes = python_oop_lesson["learning_outcomes"]
    
    # Validate each learning outcome
    for outcome_key, outcome_data in outcomes.items():
        print(f"✅ Validating outcome: {outcome_key}")
        
        # Check required fields for each outcome
        assert "description" in outcome_data, f"Missing 'description' in {outcome_key}"
        assert "mastery_level" in outcome_data, f"Missing 'mastery_level' in {outcome_key}"
        
        # Check data types
        assert isinstance(outcome_data["description"], str), f"Description must be string in {outcome_key}"
        assert isinstance(outcome_data["mastery_level"], (int, float)), f"Mastery level must be numeric in {outcome_key}"
        assert 0.0 <= outcome_data["mastery_level"] <= 1.0, f"Mastery level must be 0.0-1.0 in {outcome_key}"
    
    print(f"✅ All {len(outcomes)} learning outcomes validated successfully!")
    return True

def simulate_aims_initial_state():
    """Simulate creating initial state for AIMS graph."""
    print("\n🚀 Simulating AIMS initial state creation...")
    
    # This mimics: AIMSGraph.create_initial_state(topic, learning_outcomes)
    initial_state = {
        "topic": python_oop_lesson["topic"],
        "learning_outcomes": python_oop_lesson["learning_outcomes"],
        "current_outcome_key": "",
        "last_question": "",
        "last_response": "",
        "failed_attempts": 0,
        "feedback": ""
    }
    
    print(f"📚 Topic: {initial_state['topic']}")
    print(f"🎯 Learning Outcomes: {len(initial_state['learning_outcomes'])}")
    
    # Show learning outcomes
    for i, (key, data) in enumerate(initial_state['learning_outcomes'].items(), 1):
        print(f"   {i}. {key}: {data['description'][:50]}...")
    
    print("✅ Initial state created successfully!")
    return initial_state

def preview_assessment_flow():
    """Preview how the assessment would flow."""
    print("\n🔄 Assessment Flow Preview:")
    print("1. choose_outcome → Selects first unmastered outcome")
    print("2. generate_question → AI creates contextual question")
    print("3. assess_answer → Evaluates student response")
    print("4. Conditional routing:")
    print("   ✅ Mastery (≥80%) → provide_feedback → next outcome")
    print("   🔄 Partial (attempts <2) → rephrase_question → assess again")
    print("   📚 Struggling (attempts ≥2) → re_teach_concept → new question")
    print("5. Repeat until all outcomes mastered")

if __name__ == "__main__":
    print("🎯 AIMS Lesson Validation Tool")
    print("=" * 50)
    
    try:
        # Validate lesson structure
        validate_lesson_structure()
        
        # Simulate AIMS integration
        initial_state = simulate_aims_initial_state()
        
        # Preview assessment flow
        preview_assessment_flow()
        
        print("\n🎉 Lesson validation completed successfully!")
        print("📝 The Python OOP lesson is ready for AIMS integration.")
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        exit(1)
