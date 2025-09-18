import operator
import operator
from typing import TypedDict, Annotated, List, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Pydantic is often used here, but for simplicity, we'll use TypedDict
# from typing_extensions import TypedDict is needed for Python < 3.11

# Define the state schema for your AIMS graph
class LessonState(TypedDict):
    """Represents the state of the AIMS learning session."""
    topic: str
    learning_outcomes: Annotated[dict, operator.add]
    current_outcome_key: str
    last_question: str
    last_response: str
    failed_attempts: int
    feedback: str  # Add feedback field

class AIMSGraph:
    def __init__(self, llm=None):
        """Initializes the AIMS LangGraph."""
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        self.workflow = StateGraph(LessonState)
        self._setup_prompts()
        self._build_graph()

    def _setup_prompts(self):
        """Sets up prompt templates for different LLM tasks."""
        
        # Question generation prompt
        self.question_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert educational assessment designer. 
            Your goal is to create questions that test deep understanding and mastery of specific learning outcomes.
            
            Guidelines:
            - Ask open-ended questions that require explanation, not just recall
            - Focus on application and understanding rather than memorization
            - Make questions engaging and relevant to real-world scenarios
            - Ensure the question directly tests the specific learning outcome provided"""),
            
            HumanMessage(content="""Topic: {topic}
            Learning Outcome: {outcome}
            Previous attempts: {failed_attempts}
            
            Generate a thoughtful question to test mastery of this learning outcome. 
            The question should require the student to demonstrate understanding through explanation or application.""")
        ])
        
        # Assessment prompt
        self.assessment_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert educational assessor. Evaluate student responses for mastery.
            
            Mastery criteria:
            - Understanding of core concepts (40%)
            - Ability to explain in their own words (30%) 
            - Application or examples provided (20%)
            - Clarity and coherence (10%)
            
            Return a score between 0.0 and 1.0, where:
            - 0.8+ indicates mastery achieved
            - 0.5-0.79 indicates partial understanding
            - Below 0.5 indicates significant gaps
            
            Also provide specific feedback on what was good and what needs improvement."""),
            
            HumanMessage(content="""Learning Outcome: {outcome}
            Question Asked: {question}
            Student Response: {response}
            
            Assess this response and provide:
            1. Mastery score (0.0-1.0)
            2. Specific feedback on strengths and areas for improvement
            
            Format your response as:
            SCORE: [score]
            FEEDBACK: [detailed feedback]""")
        ])
        
        # Rephrase prompt
        self.rephrase_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert educator who excels at helping students who are struggling.
            Rephrase questions to be clearer and provide helpful hints without giving away the answer.
            
            Guidelines:
            - Break down complex concepts into smaller parts
            - Provide scaffolding or context
            - Include a gentle hint that guides thinking
            - Maintain the same learning objective"""),
            
            HumanMessage(content="""Original Question: {original_question}
            Learning Outcome: {outcome}
            Student's Previous Response: {previous_response}
            Failed Attempts: {failed_attempts}
            
            Rephrase this question to be clearer and more supportive while testing the same learning outcome.""")
        ])
        
        # Re-teaching prompt
        self.reteach_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an expert educator providing targeted re-teaching.
            Create a brief, focused explanation that addresses the specific learning outcome.
            
            Guidelines:
            - Keep explanations concise but comprehensive
            - Use examples and analogies
            - Build from basic concepts to more complex ones
            - End with a clear summary of key points"""),
            
            HumanMessage(content="""Learning Outcome: {outcome}
            Topic: {topic}
            Student has struggled with: {previous_responses}
            
            Provide a clear, engaging explanation of this concept that will help the student understand and master it.""")
        ])

    def _build_graph(self):
        """Builds the nodes and edges of the LangGraph."""
        # Define the nodes (functions that modify the state)
        self.workflow.add_node("choose_outcome", self.choose_outcome)
        self.workflow.add_node("generate_question", self.generate_question)
        self.workflow.add_node("assess_answer", self.assess_answer)
        self.workflow.add_node("rephrase_question", self.rephrase_question)
        self.workflow.add_node("re_teach_concept", self.re_teach_concept)
        self.workflow.add_node("provide_feedback", self.provide_feedback)

        # Set the entry and finish points
        self.workflow.set_entry_point("choose_outcome")
        self.workflow.add_edge("provide_feedback", "choose_outcome")

        # Define conditional edges
        self.workflow.add_conditional_edges(
            "assess_answer",
            self._route_after_assessment,
            {
                "mastery_achieved": "provide_feedback",
                "rephrase_needed": "rephrase_question",
                "reteach_needed": "re_teach_concept",
            }
        )

        # Connect other nodes
        self.workflow.add_edge("choose_outcome", "generate_question")
        self.workflow.add_edge("generate_question", "assess_answer")
        self.workflow.add_edge("rephrase_question", "assess_answer")
        self.workflow.add_edge("re_teach_concept", "generate_question")

        # Compile the graph for use
        self.compiled_graph = self.workflow.compile()
        

    def _route_after_assessment(self, state: LessonState) -> Literal["mastery_achieved", "rephrase_needed", "reteach_needed"]:
        """Conditional router based on assessment results."""
        current_outcome_info = state["learning_outcomes"][state["current_outcome_key"]]

        if current_outcome_info["mastery_level"] >= 0.8:
            return "mastery_achieved"
        elif state["failed_attempts"] < 2:  # Set a retry limit
            return "rephrase_needed"
        else:
            return "reteach_needed"

    def choose_outcome(self, state: LessonState) -> LessonState:
        """Node: Selects the next learning outcome to assess."""
        # This is where your core logic for selecting the next outcome goes.
        # For this example, let's just pick the first one with low mastery.
        for outcome_key, outcome_data in state["learning_outcomes"].items():
            if outcome_data["mastery_level"] < 0.8:
                print(f"Choosing outcome: {outcome_key}")
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
        """Node: Generates a question based on the current learning outcome."""
        if state["current_outcome_key"] == "all_mastered":
            return {
                **state,
                "last_question": "Congratulations! You have mastered all learning outcomes.",
                "feedback": "All objectives completed successfully!"
            }
            
        outcome_to_test = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_to_test]
        
        # Use LLM to generate a question for this outcome
        try:
            response = self.llm.invoke(
                self.question_prompt.format_messages(
                    topic=state["topic"],
                    outcome=outcome_data.get("description", outcome_to_test),
                    failed_attempts=state["failed_attempts"]
                )
            )
            question = response.content
        except Exception as e:
            print(f"Error generating question: {e}")
            question = f"Please explain your understanding of '{outcome_to_test}' and provide examples."
        
        print(f"Generated question: {question}")
        return {
            **state,
            "last_question": question
        }

    def assess_answer(self, state: LessonState) -> LessonState:
        """Node: Assesses the user's answer and updates mastery."""
        if not state.get("last_response"):
            # If no response yet, wait for user input
            return state
            
        outcome_key = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_key]
        
        try:
            # Use LLM to evaluate the answer
            response = self.llm.invoke(
                self.assessment_prompt.format_messages(
                    outcome=outcome_data.get("description", outcome_key),
                    question=state["last_question"],
                    response=state["last_response"]
                )
            )
            
            # Parse the LLM response
            content = response.content
            score_line = [line for line in content.split('\n') if line.startswith('SCORE:')]
            feedback_line = [line for line in content.split('\n') if line.startswith('FEEDBACK:')]
            
            if score_line:
                score_str = score_line[0].replace('SCORE:', '').strip()
                mastery_score = float(score_str)
            else:
                mastery_score = 0.5  # Default if parsing fails
                
            feedback = feedback_line[0].replace('FEEDBACK:', '').strip() if feedback_line else "Assessment completed."
            
        except Exception as e:
            print(f"Error assessing answer: {e}")
            # Fallback assessment logic
            user_response = state["last_response"].lower()
            mastery_score = 0.7 if len(user_response) > 50 else 0.3
            feedback = "Assessment completed with basic evaluation."
        
        # Update mastery level
        updated_learning_outcomes = state["learning_outcomes"].copy()
        updated_learning_outcomes[outcome_key] = {
            **outcome_data,
            "mastery_level": mastery_score
        }
        
        print(f"Assessed answer. New mastery level: {mastery_score}")
        
        if mastery_score < 0.8:
            return {
                **state,
                "learning_outcomes": updated_learning_outcomes,
                "failed_attempts": state["failed_attempts"] + 1,
                "feedback": feedback
            }
        
        return {
            **state,
            "learning_outcomes": updated_learning_outcomes,
            "failed_attempts": 0,
            "feedback": feedback
        }

    def rephrase_question(self, state: LessonState) -> LessonState:
        """Node: Rephrases the question with a hint."""
        outcome_key = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_key]
        
        try:
            response = self.llm.invoke(
                self.rephrase_prompt.format_messages(
                    original_question=state["last_question"],
                    outcome=outcome_data.get("description", outcome_key),
                    previous_response=state["last_response"],
                    failed_attempts=state["failed_attempts"]
                )
            )
            hinted_question = response.content
        except Exception as e:
            print(f"Error rephrasing question: {e}")
            hinted_question = f"Let me rephrase: {state['last_question']} (Hint: Think about the core concepts and try to explain in your own words.)"
        
        print(f"Rephrased question: {hinted_question}")
        return {
            **state,
            "last_question": hinted_question
        }

    def re_teach_concept(self, state: LessonState) -> LessonState:
        """Node: Provides a full explanation of the concept."""
        outcome_key = state["current_outcome_key"]
        outcome_data = state["learning_outcomes"][outcome_key]
        
        try:
            response = self.llm.invoke(
                self.reteach_prompt.format_messages(
                    outcome=outcome_data.get("description", outcome_key),
                    topic=state["topic"],
                    previous_responses=state["last_response"]
                )
            )
            lesson_text = response.content
        except Exception as e:
            print(f"Error generating lesson: {e}")
            lesson_text = f"Let me explain '{outcome_key}' in more detail. This concept is important because..."
        
        print(f"Providing a re-teaching lesson: {lesson_text}")
        return {
            **state,
            "feedback": lesson_text,
            "failed_attempts": 0  # Reset after re-teaching
        }

    def provide_feedback(self, state: LessonState) -> LessonState:
        """Node: Gives feedback and marks the outcome as mastered."""
        outcome_key = state["current_outcome_key"]
        positive_feedback = f"Excellent work! You've demonstrated mastery of '{outcome_key}'. Your understanding is clear and comprehensive."
        
        print("Mastery achieved! Providing positive feedback.")
        return {
            **state,
            "feedback": positive_feedback
        }

    def invoke(self, state):
        """Invokes the compiled graph."""
        # This method can be called from your FastAPI endpoint
        # The `input` should match the LessonState schema
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
            "feedback": ""
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