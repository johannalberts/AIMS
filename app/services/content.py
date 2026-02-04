"""
Learning content service - handles content generation, embedding, and retrieval.
"""
import logging
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from io import BytesIO

from openai import OpenAI
from sqlmodel import Session, select
from sqlalchemy import text
from pypdf import PdfReader

from app.models import LearningContent, LearningOutcome, Lesson, Course

logger = logging.getLogger(__name__)


class ContentService:
    """Service for managing learning content with vector embeddings."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = "text-embedding-3-small"  # More cost-effective
        self.embedding_dimensions = 1536
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text using OpenAI."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.embedding_dimensions
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def create_content_chunk(
        self,
        learning_outcome_id: int,
        content_text: str,
        content_type: str = "explanation",
        source: str = "manual",
        user_id: Optional[int] = None,
        approval_status: str = "approved",
        chunk_order: int = 0
    ) -> LearningContent:
        """Create a new learning content chunk with embedding."""
        # Get learning outcome to get lesson_id
        outcome = self.db_session.get(LearningOutcome, learning_outcome_id)
        if not outcome:
            raise ValueError(f"Learning outcome {learning_outcome_id} not found")
        
        # Generate embedding
        logger.info(f"Generating embedding for content chunk (LO: {learning_outcome_id})")
        embedding = self.generate_embedding(content_text)
        
        # Create content chunk
        content = LearningContent(
            learning_outcome_id=learning_outcome_id,
            lesson_id=outcome.lesson_id,
            content_text=content_text,
            content_type=content_type,
            chunk_order=chunk_order,
            embedding=embedding,
            source=source,
            approval_status=approval_status,
            created_by_user_id=user_id,
            approved_by_user_id=user_id if approval_status == "approved" else None,
            approved_at=datetime.utcnow() if approval_status == "approved" else None
        )
        
        self.db_session.add(content)
        self.db_session.commit()
        self.db_session.refresh(content)
        
        logger.info(f"Created content chunk {content.id} for LO {learning_outcome_id}")
        return content
    
    def generate_content_for_outcome(
        self,
        learning_outcome_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate learning content for an outcome using LLM."""
        # Get learning outcome with related data
        outcome = self.db_session.get(LearningOutcome, learning_outcome_id)
        if not outcome:
            raise ValueError(f"Learning outcome {learning_outcome_id} not found")
        
        lesson = self.db_session.get(Lesson, outcome.lesson_id)
        course = self.db_session.get(Course, lesson.course_id)
        
        # Build context for LLM
        prompt = self._build_content_generation_prompt(outcome, lesson, course)
        
        # Generate content using OpenAI
        logger.info(f"Generating content for LO {learning_outcome_id}: {outcome.description}")
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert educational content creator. Generate clear, comprehensive learning content that helps students master specific learning outcomes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            generated_content = response.choices[0].message.content
            
            # Parse the generated content into structured chunks
            chunks = self._parse_generated_content(generated_content)
            
            return {
                "learning_outcome_id": learning_outcome_id,
                "outcome_description": outcome.description,
                "generated_content": generated_content,
                "chunks": chunks,
                "status": "pending_review"
            }
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
    
    def _build_content_generation_prompt(
        self,
        outcome: LearningOutcome,
        lesson: Lesson,
        course: Course
    ) -> str:
        """Build prompt for LLM content generation."""
        prompt = f"""Generate comprehensive learning content for the following learning outcome:

**Course:** {course.title} - {course.subject}
**Lesson:** {lesson.title} (Topic: {lesson.topic})
**Learning Outcome:** {outcome.description}

Please generate the following structured sections:

1. **DEFINITION**: A clear, concise definition of the main concept (2-3 sentences)

2. **EXPLANATION**: A detailed explanation of the concept, including:
   - Why this concept is important
   - How it relates to the broader topic
   - Key principles or rules to understand
   (4-6 sentences)

3. **EXAMPLES**: Provide 2-3 concrete, practical examples that demonstrate the concept:
   - Each example should be realistic and relatable
   - Include step-by-step explanations where appropriate
   - Show different applications or scenarios

4. **COMMON ERRORS**: List 2-3 common mistakes or misconceptions students have about this concept:
   - Explain why these errors occur
   - How to avoid or correct them

5. **KEY POINTS**: Summarize 3-5 critical takeaways for mastery

Format each section clearly with the section headers above. Keep the content focused, accurate, and appropriate for the course level ({course.difficulty_level or 'intermediate'}).
"""
        return prompt
    
    def _parse_generated_content(self, content: str) -> List[Dict[str, str]]:
        """Parse generated content into structured chunks."""
        chunks = []
        
        # Simple parsing - look for section headers
        sections = {
            "DEFINITION": "definition",
            "EXPLANATION": "explanation",
            "EXAMPLES": "example",
            "COMMON ERRORS": "common_errors",
            "KEY POINTS": "key_points"
        }
        
        current_section = None
        current_text = []
        
        for line in content.split('\n'):
            # Check if line is a section header
            found_section = False
            for header, chunk_type in sections.items():
                if header in line.upper() and (line.startswith('#') or line.startswith('**') or line.strip().startswith(f"{header}")):
                    # Save previous section if exists
                    if current_section and current_text:
                        chunks.append({
                            "content_type": current_section,
                            "content_text": '\n'.join(current_text).strip(),
                            "chunk_order": len(chunks)
                        })
                    current_section = chunk_type
                    current_text = []
                    found_section = True
                    break
            
            if not found_section and current_section:
                current_text.append(line)
        
        # Add final section
        if current_section and current_text:
            chunks.append({
                "content_type": current_section,
                "content_text": '\n'.join(current_text).strip(),
                "chunk_order": len(chunks)
            })
        
        # If parsing failed, create a single chunk with all content
        if not chunks:
            chunks.append({
                "content_type": "explanation",
                "content_text": content.strip(),
                "chunk_order": 0
            })
        
        return chunks
    
    def save_generated_content(
        self,
        learning_outcome_id: int,
        chunks: List[Dict[str, str]],
        user_id: Optional[int] = None,
        approval_status: str = "approved"
    ) -> List[LearningContent]:
        """Save generated content chunks to database."""
        saved_chunks = []
        
        for chunk_data in chunks:
            chunk = self.create_content_chunk(
                learning_outcome_id=learning_outcome_id,
                content_text=chunk_data["content_text"],
                content_type=chunk_data["content_type"],
                chunk_order=chunk_data["chunk_order"],
                source="llm_generated",
                user_id=user_id,
                approval_status=approval_status
            )
            saved_chunks.append(chunk)
        
        logger.info(f"Saved {len(saved_chunks)} content chunks for LO {learning_outcome_id}")
        return saved_chunks
    
    def get_content_for_outcome(
        self,
        learning_outcome_id: int,
        approved_only: bool = True
    ) -> List[LearningContent]:
        """Retrieve all content chunks for a learning outcome."""
        query = select(LearningContent).where(
            LearningContent.learning_outcome_id == learning_outcome_id
        )
        
        if approved_only:
            query = query.where(LearningContent.approval_status == "approved")
        
        query = query.order_by(LearningContent.chunk_order)
        
        return list(self.db_session.exec(query).all())
    
    def similarity_search(
        self,
        query_text: str,
        learning_outcome_id: Optional[int] = None,
        lesson_id: Optional[int] = None,
        top_k: int = 5,
        approved_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search for relevant content."""
        # Generate embedding for query
        query_embedding = self.generate_embedding(query_text)
        
        # Build SQL query with pgvector similarity search
        # Using cosine distance (1 - cosine_similarity)
        sql_parts = [
            "SELECT id, learning_outcome_id, lesson_id, content_text, content_type,",
            "       1 - (embedding <=> :query_embedding) as similarity",
            "FROM learning_contents",
            "WHERE 1=1"
        ]
        
        params = {"query_embedding": str(query_embedding)}
        
        if learning_outcome_id:
            sql_parts.append("  AND learning_outcome_id = :learning_outcome_id")
            params["learning_outcome_id"] = learning_outcome_id
        
        if lesson_id:
            sql_parts.append("  AND lesson_id = :lesson_id")
            params["lesson_id"] = lesson_id
        
        if approved_only:
            sql_parts.append("  AND approval_status = 'approved'")
        
        sql_parts.append("ORDER BY embedding <=> :query_embedding")
        sql_parts.append(f"LIMIT {top_k}")
        
        sql = "\n".join(sql_parts)
        
        # Execute query using raw connection
        with self.db_session.connection() as conn:
            result = conn.execute(text(sql), params)
            
            # Format results
            results = []
            for row in result:
                results.append({
                    "id": row.id,
                    "learning_outcome_id": row.learning_outcome_id,
                    "lesson_id": row.lesson_id,
                    "content_text": row.content_text,
                    "content_type": row.content_type,
                    "similarity": float(row.similarity)
                })
        
        return results
    
    def delete_content_chunk(self, content_id: int) -> bool:
        """Delete a content chunk."""
        content = self.db_session.get(LearningContent, content_id)
        if content:
            self.db_session.delete(content)
            self.db_session.commit()
            logger.info(f"Deleted content chunk {content_id}")
            return True
        return False
    
    def update_content_chunk(
        self,
        content_id: int,
        content_text: Optional[str] = None,
        content_type: Optional[str] = None,
        approval_status: Optional[str] = None,
        approved_by_user_id: Optional[int] = None
    ) -> Optional[LearningContent]:
        """Update a content chunk and regenerate embedding if text changed."""
        content = self.db_session.get(LearningContent, content_id)
        if not content:
            return None
        
        # Update fields
        if content_text and content_text != content.content_text:
            content.content_text = content_text
            # Regenerate embedding
            content.embedding = self.generate_embedding(content_text)
        
        if content_type:
            content.content_type = content_type
        
        if approval_status:
            content.approval_status = approval_status
            if approval_status == "approved":
                content.approved_at = datetime.utcnow()
                if approved_by_user_id:
                    content.approved_by_user_id = approved_by_user_id
        
        content.updated_at = datetime.utcnow()
        
        self.db_session.commit()
        self.db_session.refresh(content)
        
        logger.info(f"Updated content chunk {content_id}")
        return content
    
    def process_pdf(self, pdf_file: BytesIO, learning_outcome_id: int) -> Dict[str, Any]:
        """Extract text from PDF and prepare it for chunking."""
        try:
            reader = PdfReader(pdf_file)
            
            # Extract text from all pages
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n\n"
            
            # Basic cleaning
            full_text = full_text.strip()
            
            # Auto-chunk by paragraphs (split on double newlines)
            paragraphs = [p.strip() for p in re.split(r'\n\n+', full_text) if p.strip()]
            
            # Create suggested chunks (paragraphs between 100-1000 chars)
            suggested_chunks = []
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) < 1000:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        suggested_chunks.append({
                            "content_text": current_chunk.strip(),
                            "content_type": "explanation",  # Default type
                            "chunk_order": len(suggested_chunks)
                        })
                    current_chunk = para + "\n\n"
            
            # Add final chunk
            if current_chunk:
                suggested_chunks.append({
                    "content_text": current_chunk.strip(),
                    "content_type": "explanation",
                    "chunk_order": len(suggested_chunks)
                })
            
            return {
                "learning_outcome_id": learning_outcome_id,
                "full_text": full_text,
                "num_pages": len(reader.pages),
                "suggested_chunks": suggested_chunks,
                "status": "extracted"
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            raise ValueError(f"Failed to process PDF: {str(e)}")

