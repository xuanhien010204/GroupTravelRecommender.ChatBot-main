from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from tools.tour_tools import get_tours, get_heritage_guide
from .base_agent import ToolAgentBase

class ToursSearchAgent(ToolAgentBase):
    def __init__(self):
        tools = [get_tours, get_heritage_guide]
        super().__init__(tools)
        toolNodes = ToolNode(tools)    

        graph = StateGraph(MessagesState)
        graph.add_node("tools", toolNodes)
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        self.graph = graph.compile()

    def invoke(self, initial_state: MessagesState) -> MessagesState:
        state = self.graph.invoke(initial_state)
        return state
