import operator
from typing import TypedDict, Annotated, List, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

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

class AIMSGraph:
    def __init__(self, llm):
        """Initializes the AIMS LangGraph."""
        self.llm = llm
        self.workflow = StateGraph(LessonState)
        self._build_graph()

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
                return {"current_outcome_key": outcome_key, "failed_attempts": 0}
        
        # If all outcomes are mastered, the lesson is complete.
        return {"current_outcome_key": "all_mastered"}

    def generate_question(self, state: LessonState) -> LessonState:
        """Node: Generates a question based on the current learning outcome."""
        outcome_to_test = state["current_outcome_key"]
        
        # Use an LLM to generate a question for this outcome
        # This is a placeholder for your LLM call
        question = f"Please explain the concept of '{outcome_to_test}' in your own words."
        
        print(f"Generated question: {question}")
        return {"last_question": question}

    def assess_answer(self, state: LessonState) -> LessonState:
        """Node: Assesses the user's answer and updates mastery."""
        # Use an LLM to evaluate the answer
        # For simplicity, we'll use a placeholder logic
        user_response = "Some user response"  # This would come from your FastAPI app
        
        is_correct = "div" in user_response.lower() and "section" in user_response.lower()
        
        mastery_level_change = 0.2 if is_correct else -0.1
        
        outcome_info = state["learning_outcomes"].get(state["current_outcome_key"], {})
        new_mastery_level = min(1.0, max(0.0, outcome_info.get("mastery_level", 0.0) + mastery_level_change))
        
        print(f"Assessed answer. New mastery level: {new_mastery_level}")
        
        updated_learning_outcomes = state["learning_outcomes"].copy()
        updated_learning_outcomes[state["current_outcome_key"]]["mastery_level"] = new_mastery_level
        
        if not is_correct:
            return {"learning_outcomes": updated_learning_outcomes, "failed_attempts": state["failed_attempts"] + 1}
        return {"learning_outcomes": updated_learning_outcomes, "failed_attempts": 0}

    def rephrase_question(self, state: LessonState) -> LessonState:
        """Node: Rephrases the question with a hint."""
        # Use an LLM to rephrase and add a hint.
        hinted_question = f"Let's try that again. Think about the specific purpose of the '{state['current_outcome_key']}' concept. {state['last_question']}"
        
        print(f"Rephrased question: {hinted_question}")
        return {"last_question": hinted_question}

    def re_teach_concept(self, state: LessonState) -> LessonState:
        """Node: Provides a full explanation of the concept."""
        # Use an LLM to generate a mini-lesson.
        lesson_text = f"It seems we need to review '{state['current_outcome_key']}'. Here is a brief lesson on the topic..."
        
        print(f"Providing a re-teaching lesson: {lesson_text}")
        return {"last_question": lesson_text} # This can be a text block to present to the user

    def provide_feedback(self, state: LessonState) -> LessonState:
        """Node: Gives feedback and marks the outcome as mastered."""
        print("Mastery achieved! Providing positive feedback.")
        return {"last_feedback": "Great job! You've mastered this concept."}

    def invoke(self, state):
        """Invokes the compiled graph."""
        # This method can be called from your FastAPI endpoint
        # The `input` should match the LessonState schema
        return self.compiled_graph.invoke(state)

    def get_graph(self):
        """Returns the compiled graph for use in other parts of the application."""
        return self.compiled_graph