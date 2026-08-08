from langgraph.graph import StateGraph, END, START, MessagesState
from langchain_core.messages import AIMessage
from config import OPENAI_ENDPOINT, OPENAI_API_KEY, OPENAI_DEPLOYMENT_NAME
from langchain_openai import ChatOpenAI
from tools.tour_tools import get_tours, get_heritage_guide, register_tour, get_registered_tours
from .tours_search_agent import ToursSearchAgent
from .tours_register_agent import ToursRegisterAgent
import traceback
 
class ControllerAgent():
    def __init__(self):
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_ENDPOINT,
            model=OPENAI_DEPLOYMENT_NAME
        )
        self.llmClient = llm.bind_tools([
            get_tours,
            get_heritage_guide,
            register_tour,
            get_registered_tours
        ])
 
        graph = StateGraph(MessagesState)
        graph.add_node("llm_node", self._llm_node)
        graph.add_node("handle_tool_call", self._handle_tool_calls)
        graph.add_edge(START, "llm_node")
 
        graph.add_edge("handle_tool_call", "llm_node")
        graph.add_conditional_edges("llm_node", self._should_continue)
        self.graph = graph.compile()
 
        self.tours_search_agent = ToursSearchAgent()
        self.tours_register_agent = ToursRegisterAgent()
 
 
    def _handle_tool_calls(self, state: MessagesState) -> MessagesState:
        if not state["messages"] or not state["messages"][-1].tool_calls:
            return state
 
        for tool_call in state["messages"][-1].tool_calls:
            toolName = tool_call["name"]
            if toolName in self.tours_search_agent._toolNames:
                return self.tours_search_agent.invoke(state)
            elif toolName in self.tours_register_agent._toolNames:
                return self.tours_register_agent.invoke(state)
            else:
                return { "message": [AIMessage(content=f"It looks like the tool '{toolName}' isn’t available in my current set of capabilities.")] }
        return state
 
    def invoke(self, initial_state: MessagesState) -> MessagesState:
        try:
            # Handle function calling
            state = self.graph.invoke(initial_state)
        except Exception as e:
            print(traceback.format_exc())
            return {
                "messages": [AIMessage(content=f"I encountered an issue: {str(e)}. Please try again or rephrase your request.")]
            }
        return state
   
    def _llm_node(self, state: MessagesState) -> MessagesState:
        response = self.llmClient.invoke(state["messages"])
        return {"messages": [response]}
   
    def _should_continue(self, state: MessagesState) -> str:
        if not state["messages"][-1].tool_calls:
            return END
        return "handle_tool_call"