import os

from typing import Annotated
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm = init_chat_model("openai:gpt-4.1")


class State(TypedDict):
    messages: Annotated[list, add_messages]


class AIMSGraph:
    def __init__(self, llm):
        self.llm = llm
    
    def build_graph(self):
        graph = StateGraph(State)
        graph.add_node("chatbot", self.chatbot)
        graph.add_edge(START, "chatbot")
        graph.add_edge("chatbot", END)
        return graph.compile()
    
    def chatbot(self, state: State):
        return {"messages": self.llm.invoke(state["messages"])}
