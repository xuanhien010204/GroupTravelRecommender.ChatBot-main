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
 
# --- Azure OpenAI client ---
controller_agent = ControllerAgent()

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
                               
Based on the user's request, use the appropriate function and parameters.
""")

state = {
    "messages": [system_message]
}

# --- Page config ---
st.set_page_config(page_title="Travel Chatbot", page_icon="✈️")
st.title("Travel Chatbot 🌍")
 
def main():
    # Initialize chat history and pagination state
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.tour_next_token = None
        st.session_state.heritage_next_token = None
        st.session_state.last_place = None
        st.session_state.messages.append({
            "role": "ai",
            "content": "Hello! I'm your travel assistant. I can help you with:\n"
                      "- Searching for available tours\n"
                      "- Finding heritage guide information about places\n"
                      "- Checking your registered tours\n"
                      "- Registering for a tour\n\n"
                      "You can ask me about tours or cultural heritage information for any place. What would you like to know?"
        })
 
    # TODO: Voice to text input
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
 
    # Chat input
    if prompt := st.chat_input("What can I help you with?"):
        with st.chat_message("human"):
            st.write(prompt)
            state["messages"].append(HumanMessage(content=prompt))
            st.session_state.messages.append({"role": "human", "content": prompt})
 
        # Show assistant response
        with st.chat_message("ai"):
            with st.spinner("Thinking..."):
                # Determine which function to use based on user input
                final_state = controller_agent.invoke(
                    initial_state=state
                )
                content = final_state["messages"][-1].content
                st.write(content)
                st.session_state.messages.append({"role": "ai", "content": content})
                state["messages"].append(AIMessage(content=content))

if __name__ == "__main__":
    main()
        