import os
from typing import TypedDict, List, Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import psycopg
from psycopg.rows import dict_row

# Load environment variables
load_dotenv()

# Define the state schema for your AIMS graph
class LessonState(TypedDict):
    """Represents the state of the AIMS learning session."""
    topic: str
    learning_outcomes: dict  # Remove the Annotated operator.add - we'll handle updates manually
    current_outcome_key: str
    last_question: str
    last_response: str
    failed_attempts: int
    feedback: str  # Add feedback field
    concepts_covered: dict  # Track which concepts have been addressed per outcome

class AIMSGraph:
    def __init__(self, llm=None, checkpointer=None):
        """Initializes the AIMS LangGraph with PostgreSQL checkpointing."""
        # Get API key and validate
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        print(f"🔑 OpenAI API Key loaded: {api_key[:20]}..." if api_key else "❌ No API key found")
        
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.7, api_key=api_key)
        
        # Initialize checkpointer if not provided
        if checkpointer is None:
            db_uri = os.getenv("DATABASE_URL", "postgresql://aims_user:aims_password@db:5432/aims_db")
            print(f"📊 Initializing PostgreSQL checkpointer: {db_uri.split('@')[1] if '@' in db_uri else db_uri}")
            
            try:
                # Create connection for checkpointer using psycopg3
                conn = psycopg.connect(db_uri, row_factory=dict_row, autocommit=True)
                self.checkpointer = PostgresSaver(conn)
                # Setup checkpoint tables (creates them if they don't exist)
                self.checkpointer.setup()
                print("✅ PostgreSQL checkpointer initialized successfully")
            except Exception as e:
                print(f"⚠️  Warning: Could not initialize checkpointer: {e}")
                self.checkpointer = None
        else:
            self.checkpointer = checkpointer
        
        self.workflow = StateGraph(LessonState)
        self._setup_prompts()
        self._build_graph()

    def _setup_prompts(self):
        """Sets up prompt templates for different LLM tasks."""
        
        # Question generation prompt
        self.question_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educational assessment designer creating questions for a conversational chat-based assessment.
            
            CRITICAL REQUIREMENTS:
            - Generate SHORT, focused questions (1-2 sentences maximum)
            - Focus on ONE key concept at a time, not all concepts together
            - Use a conversational, friendly tone
            - Ask open-ended questions that require brief explanation
            - Make questions practical and relatable to real-world scenarios
            - Avoid complex multi-part questions
            
            GOOD EXAMPLES:
            - "What are the main health benefits of growing your own vegetables?"
            - "Can you explain what a raised bed garden is and when you might use one?"
            - "How does composting help improve soil quality?"
            
            BAD EXAMPLES (too long/complex):
            - "Explain the fundamental benefits of vegetable gardening, describe different garden types, and discuss organic practices..."
            - Multi-paragraph scenario questions with multiple sub-questions"""),
            
            ("human", """Topic: {topic}
            Learning Outcome: {outcome}
            Key Concepts to Test: {key_concepts}
            Previous attempts: {failed_attempts}
            
            Generate ONE short, focused question (1-2 sentences max) that tests understanding of ONE of the key concepts listed above.
            Pick the most important concept to test first, or cycle through them if there have been previous attempts.
            Keep it conversational and concise.""")
        ])
        
        # Assessment prompt
        self.assessment_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educational assessor for a conversational chat-based assessment.
            Evaluate student responses to determine which KEY CONCEPTS they have demonstrated understanding of.
            
            CRITICAL: Your job is to identify WHICH key concepts the student has addressed, not to judge elaboration.
            
            Scoring guide:
            - Award points for each key concept demonstrated (divide 1.0 by number of concepts)
            - Brief but accurate mentions COUNT as understanding
            - Focus on conceptual coverage, not length or detail
            
            Example: If there are 3 key concepts and student addresses 2 of them:
            - Score: 0.67 (2/3 concepts)
            
            CRITICAL: Provide ONLY ONE numeric score between 0.0 and 1.0, not a range."""),
            
            ("human", """Learning Outcome: {outcome}
            
            Key Concepts to Check (student needs to address ALL of these):
            {key_concepts}
            
            Previous concepts already covered in this conversation:
            {concepts_covered}
            
            Question Asked: {question}
            Student's Current Response: {response}
            
            Assess this response:
            1. Which key concepts (if any) did the student demonstrate understanding of in THIS response?
            2. Combined with previously covered concepts, what percentage of total concepts are now covered?
            
            Format your response EXACTLY as follows:
            CONCEPTS_ADDRESSED: [list the specific concepts from the key concepts that were addressed in this response]
            SCORE: [single number 0.0-1.0 representing total % of concepts covered including previous responses]
            FEEDBACK: [1-2 sentences acknowledging what they got right and what's still missing, if anything]
            
            Example:
            CONCEPTS_ADDRESSED: vegetable gardening benefits, sustainability
            SCORE: 0.67
            FEEDBACK: Great! You've covered the benefits and sustainability aspects. We still need to explore the types of gardens.""")
        ])
        
        # Rephrase prompt
        self.rephrase_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educator helping students in a conversational chat assessment.
            Rephrase questions to be clearer and provide gentle hints without giving away the answer.
            
            Guidelines:
            - Keep the rephrased question SHORT (1-2 sentences)
            - Break down the concept into simpler terms
            - Provide a gentle hint or example to guide thinking
            - Maintain a supportive, conversational tone"""),
            
            ("human", """Original Question: {original_question}
            Learning Outcome: {outcome}
            Student's Previous Response: {previous_response}
            Failed Attempts: {failed_attempts}
            
            Rephrase this question to be clearer and more supportive (1-2 sentences max).
            Add a gentle hint based on what the student seems to be missing.""")
        ])
        
        # Follow-up question prompt (for partial understanding)
        self.followup_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educator creating targeted follow-up questions for students who partially understand a concept.
            
            CRITICAL REQUIREMENTS:
            - Acknowledge what the student got RIGHT first (be specific!)
            - Ask a focused follow-up about the MISSING key concepts
            - Keep it conversational and encouraging (2-3 sentences max)
            - Guide them toward completeness without giving away the answer
            
            GOOD EXAMPLE:
            "Great! You mentioned cost savings and freshness, which are key benefits. Can you also explain how growing your own vegetables impacts your health and the environment?"
            
            BAD EXAMPLE:
            "What are some benefits of growing your own vegetables at home?" (same question repeated)"""),
            
            ("human", """Learning Outcome: {outcome}
            All Key Concepts to Cover: {key_concepts}
            Concepts Already Addressed: {concepts_covered}
            Previous Question: {previous_question}
            Student's Response: {student_response}
            Assessment Feedback: {feedback}
            
            Generate a follow-up question (2-3 sentences) that:
            1. Acknowledges the concepts they've covered so far
            2. Asks SPECIFICALLY about the missing concepts
            3. Makes it clear what still needs to be addressed
            Keep it encouraging and conversational.""")
        ])
        
        # Re-teaching prompt
        self.reteach_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educator providing brief, focused explanations in a conversational chat.
            
            Guidelines:
            - Keep explanations CONCISE (3-4 sentences maximum)
            - Focus on ONE key concept at a time
            - Use simple, relatable examples
            - End with a clear takeaway point
            - Write in a friendly, conversational tone"""),
            
            ("human", """Learning Outcome: {outcome}
            Topic: {topic}
            Student has struggled with: {previous_responses}
            
            Provide a brief, clear explanation (3-4 sentences max) to help them understand this concept.
            Use a simple example if it helps.""")
        ])

    def _build_graph(self):
        """Builds the nodes and edges of the LangGraph with simplified workflow."""
        # Define the nodes (only essential ones)
        self.workflow.add_node("choose_outcome", self.choose_outcome)
        self.workflow.add_node("generate_question", self.generate_question)
        self.workflow.add_node("assess_answer", self.assess_answer)

        # Set the entry point
        self.workflow.set_entry_point("choose_outcome")

        # Route from choose_outcome: if there's a last_response, assess it first
        self.workflow.add_conditional_edges(
            "choose_outcome",
            self._route_from_choose_outcome,
            {
                "generate_question": "generate_question",
                "assess_answer": "assess_answer"
            }
        )

        # After assessment, check if we're done or need another question
        self.workflow.add_conditional_edges(
            "assess_answer",
            self._route_after_assessment,
            {
                "done": END,
                "continue": "choose_outcome"
            }
        )

        # After generating question, stop and wait for user input
        self.workflow.add_edge("generate_question", END)

        # Compile the graph WITH checkpointer for state persistence
        if self.checkpointer:
            self.compiled_graph = self.workflow.compile(checkpointer=self.checkpointer)
            print("✅ Graph compiled with PostgreSQL checkpointing enabled")
        else:
            self.compiled_graph = self.workflow.compile()
            print("⚠️  Graph compiled without checkpointing (will not persist state)")
        

    def _route_from_choose_outcome(self, state: LessonState) -> Literal["generate_question", "assess_answer"]:
        """Route from choose_outcome based on whether we have a user response to assess."""
        # If there's a last_response that hasn't been assessed yet, go to assess_answer
        if state.get("last_response") and state.get("last_response").strip():
            return "assess_answer"
        return "generate_question"
        

    def _route_after_assessment(self, state: LessonState) -> Literal["done", "continue"]:
        """Route after assessment - continue or end."""
        # Check if all outcomes are mastered
        if state.get("current_outcome_key") == "all_mastered":
            return "done"
        return "continue"

    def choose_outcome(self, state: LessonState) -> LessonState:
        """Node: Selects the next learning outcome to assess."""
        print(f"[GRAPH] choose_outcome called. Current outcomes: {list(state['learning_outcomes'].keys())}")
        # This is where your core logic for selecting the next outcome goes.
        # For this example, let's just pick the first one with low mastery.
        for outcome_key, outcome_data in state["learning_outcomes"].items():
            mastery = outcome_data["mastery_level"]
            print(f"[GRAPH] Checking {outcome_key}: mastery={mastery}")
            if mastery < 0.8:
                print(f"[GRAPH] Choosing outcome: {outcome_key} (mastery={mastery} < 0.8)")
                # Return only the fields we want to update
                return {
                    **state,  # Keep all existing state
                    "current_outcome_key": outcome_key, 
                    "failed_attempts": 0
                }
        
        # If all outcomes are mastered, the lesson is complete.
        return {
            **state,
            "current_outcome_key": "all_mastered"
        }

    def generate_question(self, state: LessonState) -> LessonState:
        """Node: Generates next question, combining with feedback if following an answer."""
        print(f"[GRAPH] generate_question called for outcome: {state.get('current_outcome_key')}")
        
        if state["current_outcome_key"] == "all_mastered":
            return {
                **state,
                "last_question": "",
                "feedback": "🎉 Congratulations! You have mastered all learning outcomes!"
            }
            
        outcome_to_test = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_to_test]
        mastery_level = outcome_data.get("mastery_level", 0.0)
        
        # Get key concepts
        key_concepts = outcome_data.get("key_concepts", "")
        if isinstance(key_concepts, list):
            key_concepts_list = key_concepts
            key_concepts_str = ", ".join(key_concepts)
        elif isinstance(key_concepts, str) and key_concepts:
            key_concepts_list = [k.strip() for k in key_concepts.split(',') if k.strip()]
            key_concepts_str = key_concepts
        else:
            key_concepts_list = []
            key_concepts_str = "General understanding of the learning outcome"
        
        # Get concepts already covered
        concepts_covered = state.get("concepts_covered", {}).get(outcome_to_test, [])
        concepts_remaining = [c for c in key_concepts_list if c not in concepts_covered]
        
        # Determine if this follows an assessment
        # Check if there's feedback from a recent assessment
        has_previous_answer = state.get("feedback") and mastery_level > 0
        
        try:
            if has_previous_answer and mastery_level < 0.8 and concepts_remaining:
                # Create combined acknowledgment + next question
                print(f"[GRAPH] Generating combined feedback+question (mastery={mastery_level}, concepts_covered={len(concepts_covered)}/{len(key_concepts_list)})")
                
                prompt = f"""You are an encouraging tutor. The student just answered a question about {outcome_data.get("description", outcome_to_test)}.

Assessment Result: {state.get("feedback", "")}
Mastery Level: {int(mastery_level * 100)}%

Key Concepts for this Learning Outcome:
- All: {key_concepts_str}
- Already Covered: {', '.join(concepts_covered) if concepts_covered else 'None yet'}
- Still Needed: {', '.join(concepts_remaining)}

Create a SINGLE, BRIEF response (2-3 sentences max) that:
1. Briefly acknowledges what they understood (based on the assessment)
2. Asks about the NEXT uncovered concept from the "Still Needed" list

Be conversational and encouraging. Focus on moving forward to the next concept."""

                response = self.llm.invoke([("human", prompt)])
                combined_message = response.content
                
            elif mastery_level >= 0.8:
                # Mastery achieved - just feedback, no next question for this outcome
                combined_message = f"✅ Excellent work! You've mastered {outcome_data.get('description', outcome_to_test)}!"
                
            else:
                # Fresh question for new outcome or first question
                print(f"[GRAPH] Generating fresh question")
                response = self.llm.invoke(
                    self.question_prompt.format_messages(
                        topic=state["topic"],
                        outcome=outcome_data.get("description", outcome_to_test),
                        key_concepts=key_concepts_str,
                        failed_attempts=state["failed_attempts"]
                    )
                )
                combined_message = response.content
                
        except Exception as e:
            print(f"Error generating question: {e}")
            combined_message = f"Please explain your understanding of '{outcome_to_test}' and provide examples."
        
        print(f"[GRAPH] Generated message: {combined_message[:100]}...")
        return {
            **state,
            "last_question": combined_message,
            "feedback": "",  # Clear feedback after using it to prevent reuse
            "last_response": ""  # Clear last_response after using it in combined message
        }

    def assess_answer(self, state: LessonState) -> LessonState:
        """Node: Assesses the user's answer and updates mastery."""
        if not state.get("last_response"):
            # If no response yet, wait for user input
            return state
            
        outcome_key = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_key]
        
        # Get key concepts
        key_concepts = outcome_data.get("key_concepts", "")
        if isinstance(key_concepts, list):
            key_concepts_str = ", ".join(key_concepts)
        elif not key_concepts:
            key_concepts_str = "General understanding"
        else:
            key_concepts_str = key_concepts
        
        # Get previously covered concepts for this outcome
        concepts_covered = state.get("concepts_covered", {}).get(outcome_key, [])
        concepts_covered_str = ", ".join(concepts_covered) if concepts_covered else "None yet"
        
        try:
            # Use LLM to evaluate the answer
            response = self.llm.invoke(
                self.assessment_prompt.format_messages(
                    outcome=outcome_data.get("description", outcome_key),
                    key_concepts=key_concepts_str,
                    concepts_covered=concepts_covered_str,
                    question=state["last_question"],
                    response=state["last_response"]
                )
            )
            
            # Parse the LLM response
            content = response.content
            print(f"[GRAPH] Assessment response: {content}")
            
            # Extract concepts addressed
            concepts_line = [line for line in content.split('\n') if line.startswith('CONCEPTS_ADDRESSED:')]
            new_concepts = []
            if concepts_line:
                concepts_str = concepts_line[0].replace('CONCEPTS_ADDRESSED:', '').strip()
                new_concepts = [c.strip() for c in concepts_str.split(',') if c.strip() and c.strip().lower() != 'none']
            
            # Extract score
            score_line = [line for line in content.split('\n') if line.startswith('SCORE:')]
            if score_line:
                score_str = score_line[0].replace('SCORE:', '').strip()
                mastery_score = float(score_str)
            else:
                mastery_score = 0.5  # Default if parsing fails
            
            # Extract feedback
            feedback_line = [line for line in content.split('\n') if line.startswith('FEEDBACK:')]
            feedback = feedback_line[0].replace('FEEDBACK:', '').strip() if feedback_line else "Assessment completed."
            
        except Exception as e:
            print(f"Error assessing answer: {e}")
            import traceback
            traceback.print_exc()
            # Fallback assessment logic
            user_response = state["last_response"].lower()
            mastery_score = 0.7 if len(user_response) > 50 else 0.3
            feedback = "Assessment completed with basic evaluation."
            new_concepts = []
        
        # Update concepts covered for this outcome
        all_concepts_covered = state.get("concepts_covered", {}).copy()
        outcome_concepts = set(all_concepts_covered.get(outcome_key, []))
        outcome_concepts.update(new_concepts)
        all_concepts_covered[outcome_key] = list(outcome_concepts)
        
        # Update mastery level
        updated_learning_outcomes = state["learning_outcomes"].copy()
        updated_learning_outcomes[outcome_key] = {
            **outcome_data,
            "mastery_level": mastery_score
        }
        
        print(f"[GRAPH] Assessed answer for {outcome_key}. Score: {mastery_score}, Concepts covered: {list(outcome_concepts)}, Feedback: {feedback[:100]}")
        
        if mastery_score < 0.8:
            return {
                **state,
                "learning_outcomes": updated_learning_outcomes,
                "failed_attempts": state["failed_attempts"] + 1,
                "feedback": feedback,
                "concepts_covered": all_concepts_covered,
                "last_response": ""  # Clear to prevent re-assessment
            }
        
        return {
            **state,
            "learning_outcomes": updated_learning_outcomes,
            "failed_attempts": 0,
            "feedback": feedback,
            "concepts_covered": all_concepts_covered,
            "last_response": ""  # Clear to prevent re-assessment
        }

    def invoke(self, state, config=None):
        """Invokes the compiled graph with optional config for checkpointing."""
        # This method can be called from your FastAPI endpoint
        # The `input` should match the LessonState schema
        # Config can include thread_id for state persistence
        if config:
            return self.compiled_graph.invoke(state, config)
        return self.compiled_graph.invoke(state)
    
    def submit_response(self, state: LessonState, user_response: str) -> LessonState:
        """Submit a user response and continue the assessment."""
        # Update state with user response
        updated_state = {
            **state,
            "last_response": user_response
        }
        
        # Continue from assess_answer node
        return self.compiled_graph.invoke(updated_state)

    def get_graph(self):
        """Returns the compiled graph for use in other parts of the application."""
        return self.compiled_graph

    @staticmethod
    def create_initial_state(topic: str, learning_outcomes: dict) -> LessonState:
        """Helper method to create initial lesson state."""
        return {
            "topic": topic,
            "learning_outcomes": learning_outcomes,
            "current_outcome_key": "",
            "last_question": "",
            "last_response": "",
            "failed_attempts": 0,
            "feedback": "",
            "concepts_covered": {}  # Track concepts per outcome
        }

# Example usage and testing
if __name__ == "__main__":
    # Example learning outcomes for HTML lesson
    html_outcomes = {
        "html_semantics": {
            "description": "Understanding HTML semantic elements and their proper usage",
            "mastery_level": 0.0
        },
        "html_structure": {
            "description": "Understanding HTML document structure and hierarchy",
            "mastery_level": 0.0
        },
        "html_accessibility": {
            "description": "Understanding HTML accessibility features and best practices",
            "mastery_level": 0.0
        }
    }
    
    # Create initial state
    initial_state = AIMSGraph.create_initial_state(
        topic="HTML Fundamentals",
        learning_outcomes=html_outcomes
    )
    
    # Initialize the graph (Note: requires OpenAI API key in environment)
    try:
        aims_graph = AIMSGraph()
        
        # Start the assessment
        result = aims_graph.invoke(initial_state)
        print("Assessment started!")
        print(f"Question: {result.get('last_question', 'No question generated')}")
        
    except Exception as e:
        print(f"Error initializing AIMS graph: {e}")
        print("Make sure you have OPENAI_API_KEY set in your environment variables")