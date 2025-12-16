import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
import logging

logger = logging.getLogger(__name__)

# Dummy Sensitive Tool
@tool
def delete_database(table_name: str) -> str:
    """Deletes a database table. Extremely dangerous."""
    return f"SIMULATED: Table {table_name} has been deleted."

@tool
def search_knowledge_base(query: str) -> str:
    """Searches the internal knowledge base."""
    return f"Results for {query}: [Doc 1: Security Protocols]"

def build_agent():
    # 1. LLM
    # User choice: gemini-2.5-flash-lite
    # Provider: Vertex AI Only
    
    model_name = "gemini-2.5-flash-lite"

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        max_retries=1, 
        timeout=600
    )

    # 2. Tools
    tools = [delete_database, search_knowledge_base]

    # 3. Agent Construction
    agent_graph = create_react_agent(llm, tools) 
    
    return agent_graph
