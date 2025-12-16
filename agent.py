import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

# Dummy Sensitive Tool
@tool
def delete_database(table_name: str) -> str:
    """Deletes a database table. Extremely dangerous."""
    return f"SIMULATED: Table {table_name} has been deleted."

@tool
def search_knowledge_base(query: str) -> str:
    """Searches the internal knowledge base."""
    return f"Results for {query}: [Doc 1: Security Protocols]"

import re
import time

import asyncio

import random

# Global state for rate limiting
GLOBAL_RETRY_UNTIL = 0.0
GLOBAL_UPDATE_LOCK = asyncio.Lock() # To ensure only one thread updates the time/counts down
CONCURRENCY_LIMITER = asyncio.Semaphore(5) # Throttle to max 5 active Gemini calls

class RateLimitedGemini(ChatGoogleGenerativeAI):
    def invoke(self, *args, **kwargs):
        # Sync fallback (Warn: doesn't use the async locks)
        global GLOBAL_RETRY_UNTIL
        while True:
            wait_time = GLOBAL_RETRY_UNTIL - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            try:
                return super().invoke(*args, **kwargs)
            except Exception as e:
                self._handle_exception(e)

    async def ainvoke(self, *args, **kwargs):
        global GLOBAL_RETRY_UNTIL
        while True:
            # 1. Check Global Backoff
            wait_time = GLOBAL_RETRY_UNTIL - time.time()
            if wait_time > 0:
                # If wait is needed, we sleep. 
                # We do NOT print here to avoid spamming 20 lines of "Blocked".
                # The thread running the countdown handles the printing.
                await asyncio.sleep(wait_time + random.uniform(0.1, 0.5)) 
                continue

            try:
                # 2. Throttle concurrency
                async with CONCURRENCY_LIMITER:
                    # Double check time after acquiring semaphore (in case we waited long)
                    if GLOBAL_RETRY_UNTIL - time.time() > 0:
                        continue 
                        
                    return await super().ainvoke(*args, **kwargs)
                
            except Exception as e:
                # 3. Handle Errors with Lock
                await self._handle_async_exception(e)

    async def _handle_async_exception(self, e):
        global GLOBAL_RETRY_UNTIL
        error_str = str(e)
        
        if "429" in error_str:
            match = re.search(r"retry in (\d+\.?\d*)s", error_str)
            if match:
                retry_delay = float(match.group(1)) + 1.0 # 1s buffer
                
                # Critical Section: Only one thread updates the global timer and shows countdown
                async with GLOBAL_UPDATE_LOCK:
                    # Re-check status inside lock (race condition check)
                    current_wait = GLOBAL_RETRY_UNTIL - time.time()
                    
                    if current_wait < retry_delay: 
                        # We are the first to report this (or the longest wait).
                        # Update the global blocker.
                        GLOBAL_RETRY_UNTIL = time.time() + retry_delay
                        
                        # WE are the UI thread now. Show the countdown.
                        print(f"RATE LIMIT HIT: API asked to retry in {match.group(1)}s. GLOBAL PAUSE active.")
                        await self._wait_with_visual_countdown(retry_delay)
                    else:
                        # Someone else already updated the timer to a longer/later time.
                        # We just ignore this error and let the main loop wait.
                        # print("Another thread already triggered backoff. Joining wait...")
                        pass
                return
        raise e

    async def _wait_with_visual_countdown(self, duration):
        # Countdown loop
        end_time = time.time() + duration
        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            print(f"Retrying in {int(remaining)} seconds...   ", end='\r')
            await asyncio.sleep(min(1.0, remaining))
        print("Retrying now!                                ")

    def _handle_exception(self, e):
        # Sync version (simplified, no visual loop needed for main.py async path)
        global GLOBAL_RETRY_UNTIL
        error_str = str(e)
        if "429" in error_str:
            match = re.search(r"retry in (\d+\.?\d*)s", error_str)
            if match:
                retry_delay = float(match.group(1)) + 1.0
                GLOBAL_RETRY_UNTIL = time.time() + retry_delay
                print(f"RATE LIMIT HIT: Global Lock set for {retry_delay:.2f}s.")
                time.sleep(retry_delay)
                return
        raise e

def build_agent():
    # 1. LLM
    # Uses GOOGLE_API_KEY from environment automatically
    # Switch to Flash Lite Preview for better quotas + Auto Retries
    llm = RateLimitedGemini(
        model="gemini-2.0-flash-lite-preview-02-05", 
        temperature=0,
        max_retries=0, # Disable default retries so we can use our smart logic
        timeout=600
    )

    # 2. Tools
    tools = [delete_database, search_knowledge_base]

    # 3. System Message (State Modifier)
    system_message = "You are a helpful AI assistant. You have access to tools. Use them wisely."

    # 4. Agent Construction (LangGraph)
    # create_react_agent returns a CompiledGraph which is the new "AgentExecutor"
    # Fallback to passing a prompt directly or just reliance on model behavior if kwargs fail
    # Note: For strict system prompting in prebuilt agents, we can modify the LLM itself or use 'state_modifier' if valid.
    # Since specific kwargs proved unstable across versions, we will inject it into the model.
    
    agent_graph = create_react_agent(llm, tools) # Trying minimal arguments 
    
    return agent_graph
