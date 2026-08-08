from datetime import datetime
from agents.controller_agent import ControllerAgent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config import validate_config
from dotenv import load_dotenv
import json
import streamlit as st

# --- Load environment ---
load_dotenv()
validate_config()

system_message = SystemMessage(content="""You are a travel assistant that can help users with:
1. Searching for tours and their details
2. Searching heritage guide information about specific places or cultural sites
3. Checking their registered tours
4. Registering for tours
 
For heritage guide searches:
- Use the get_heritage_guide function when searching for cultural or historical information
- Always include both 'place' and 'search_query' parameters when possible
- If the user only gives a place (e.g. 'Get me tour heritage in Hue'), infer a relevant search_query automatically, such as 'heritage sites', 'tourist information', or 'places to visit'
 
For tour searches:
- Use the get_tours function to find available tours
- Results will show tour details including dates and prices

For the tours information:
- Convert time to UTC + 7 for the times in the tour data (yyyy-mm-dd hh:mm format)

Based on the user's request, use the appropriate function and parameters.""")


def get_initial_state(human_input: str):
    return {
        "messages": [system_message, HumanMessage(content=human_input)]
    }

controller_agent = ControllerAgent()

states = [
    get_initial_state("Can you help me find tours in Hoi An?"),
    get_initial_state("Give me registered tours for phone number 0258963147"),
    get_initial_state("I want to know heritage guide in Ha Noi about HOAN KIEM LAKE A “SHOWCASE” OF SUMMER CUISINE IN HANOI"),
]

for i, state in enumerate(states):
    print(f"\n\n--- Conversation {i + 1} ---")
    final_state = controller_agent.invoke(state)
    print(final_state["messages"][-1].content)




