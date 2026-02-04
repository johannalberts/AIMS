"""
Test script for learning content management features.
Tests content upload, generation, and retrieval.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from app.database import get_session
from app.services.content import ContentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_manual_content_upload():
    """Test manual content upload with embedding generation."""
    logger.info("\n=== Test 1: Manual Content Upload ===")
    
    session = next(get_session())
    content_service = ContentService(session)
    
    # Create a test content chunk for learning outcome 1 (class_definition)
    test_content = """
    A class in Python is defined using the 'class' keyword followed by the class name. 
    The class name should follow PascalCase convention (first letter of each word capitalized).
    
    Example:
    class MyClass:
        pass
    
    This creates a simple class with no attributes or methods.
    """
    
    try:
        chunk = content_service.create_content_chunk(
            learning_outcome_id=1,
            content_text=test_content.strip(),
            content_type="example",
            source="manual",
            user_id=1,  # Assuming admin user with id=1
            approval_status="approved"
        )
        
        logger.info(f"✅ Created content chunk ID: {chunk.id}")
        logger.info(f"   - Learning Outcome: {chunk.learning_outcome_id}")
        logger.info(f"   - Content Type: {chunk.content_type}")
        logger.info(f"   - Embedding dimensions: {len(chunk.embedding) if chunk.embedding else 'None'}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create content chunk: {e}")
        return False


def test_content_retrieval():
    """Test retrieving content for a learning outcome."""
    logger.info("\n=== Test 2: Content Retrieval ===")
    
    session = next(get_session())
    content_service = ContentService(session)
    
    try:
        chunks = content_service.get_content_for_outcome(
            learning_outcome_id=1,
            approved_only=True
        )
        
        logger.info(f"✅ Retrieved {len(chunks)} content chunks for LO 1")
        for chunk in chunks:
            logger.info(f"   - Chunk {chunk.id}: {chunk.content_type} ({len(chunk.content_text)} chars)")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to retrieve content: {e}")
        return False


def test_similarity_search():
    """Test vector similarity search."""
    logger.info("\n=== Test 3: Similarity Search ===")
    
    session = next(get_session())
    content_service = ContentService(session)
    
    # First, check if there's any content
    chunks = content_service.get_content_for_outcome(1, approved_only=False)
    if not chunks:
        logger.warning("⚠️  No content available for similarity search test")
        return True
    
    try:
        # Search for content related to "how to define a class"
        query = "How do I define a class in Python?"
        results = content_service.similarity_search(
            query_text=query,
            learning_outcome_id=1,
            top_k=3
        )
        
        logger.info(f"✅ Found {len(results)} similar content chunks for query: '{query}'")
        for i, result in enumerate(results):
            logger.info(f"   {i+1}. Similarity: {result['similarity']:.4f}")
            logger.info(f"      Type: {result['content_type']}")
            logger.info(f"      Preview: {result['content_text'][:100]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed similarity search: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_content_generation():
    """Test AI content generation."""
    logger.info("\n=== Test 4: AI Content Generation ===")
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("⚠️  OPENAI_API_KEY not set, skipping content generation test")
        return True
    
    session = next(get_session())
    content_service = ContentService(session)
    
    try:
        # Generate content for learning outcome 2 (methods_and_self)
        result = content_service.generate_content_for_outcome(
            learning_outcome_id=2,
            user_id=1
        )
        
        logger.info(f"✅ Generated content for LO 2: {result['outcome_description']}")
        logger.info(f"   Status: {result['status']}")
        logger.info(f"   Generated {len(result['chunks'])} content chunks:")
        
        for chunk in result['chunks']:
            logger.info(f"   - {chunk['content_type']}: {len(chunk['content_text'])} chars")
        
        # Optionally save the generated content
        logger.info("\n   Saving generated content...")
        saved_chunks = content_service.save_generated_content(
            learning_outcome_id=2,
            chunks=result['chunks'],
            user_id=1,
            approval_status="approved"
        )
        logger.info(f"   ✅ Saved {len(saved_chunks)} chunks")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to generate content: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_content_update():
    """Test updating existing content."""
    logger.info("\n=== Test 5: Content Update ===")
    
    session = next(get_session())
    content_service = ContentService(session)
    
    # Get first chunk for LO 1
    chunks = content_service.get_content_for_outcome(1, approved_only=False)
    if not chunks:
        logger.warning("⚠️  No content available for update test")
        return True
    
    try:
        chunk = chunks[0]
        original_text = chunk.content_text
        
        updated_chunk = content_service.update_content_chunk(
            content_id=chunk.id,
            content_text=original_text + "\n\n[Updated for testing]",
            content_type="explanation"
        )
        
        logger.info(f"✅ Updated content chunk {chunk.id}")
        logger.info(f"   - Original length: {len(original_text)} chars")
        logger.info(f"   - Updated length: {len(updated_chunk.content_text)} chars")
        logger.info(f"   - New type: {updated_chunk.content_type}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update content: {e}")
        return False


def run_all_tests():
    """Run all content management tests."""
    logger.info("🧪 Starting Content Management Tests\n")
    logger.info("=" * 60)
    
    tests = [
        ("Manual Content Upload", test_manual_content_upload),
        ("Content Retrieval", test_content_retrieval),
        ("Similarity Search", test_similarity_search),
        ("AI Content Generation", test_content_generation),
        ("Content Update", test_content_update),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
    else:
        logger.info(f"⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
