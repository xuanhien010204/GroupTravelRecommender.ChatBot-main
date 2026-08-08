from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from tools.tour_tools import register_tour, get_registered_tours
from .base_agent import ToolAgentBase

class ToursRegisterAgent(ToolAgentBase):
    def __init__(self):
        tools = [register_tour, get_registered_tours]
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
