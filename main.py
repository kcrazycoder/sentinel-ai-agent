import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize Datadog Tracing (Handled by ddtrace-run in Dockerfile)
# from ddtrace import patch_all
# patch_all()

# Configure Logging
# Using simplified format as requested by user
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

from agent import build_agent

agent_executor = None
SUSPENDED = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load Agent
    global agent_executor
    logger.info("Initializing SentinelAI Agent...")
    agent_executor = build_agent()
    yield
    # Shutdown
    logger.info("Shutting down SentinelAI...")

app = FastAPI(title="SentinelAI", version="1.0.0", lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "sentinel-ai-agent"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main entry point for interacting with the SentinelAI Agent.
    traces and metrics will be captured automatically by ddtrace.
    """
    logger.info(f"Received chat request from {request.user_id}: {request.message}")
    
    if SUSPENDED:
        raise HTTPException(status_code=503, detail="Service Suspended by Security Monitor")

    if not agent_executor:
        raise HTTPException(status_code=503, detail="Agent not initialized")
        
    # Execute Agent
    try:
        from callbacks import DatadogCallbackHandler
        
        # LangGraph invoke returns a state dictionary (usually 'messages')
        # We pass the input as a user message
        inputs = {"messages": [("user", request.message)]}
        config = {"callbacks": [DatadogCallbackHandler()]}
        
        result = await agent_executor.ainvoke(inputs, config=config)
        
        last_message = result['messages'][-1]
        response_text = last_message.content
        logger.info(f"Agent Response: {response_text}")

        # Custom Observability: Tag Refusals on the Span (since Logs are disabled)
        try:
            from ddtrace import tracer
            current_span = tracer.current_span()
            if current_span:
                # Simple keyword matching for safety refusals
                if any(phrase in response_text.lower() for phrase in ["cannot fulfill", "dangerous", "prohibited", "illegal"]):
                    current_span.set_tag("sentinel.refusal", "true")
        except ImportError:
            pass
        
        return {"response": response_text}
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
             logger.info("Handling 429/ResourceExhausted Error, returning 429")
             raise HTTPException(status_code=429, detail="Upstream LLM Rate Limit Exceeded. Please retry later.")
        logger.error(f"Returning 500 for error: {error_str[:100]}...")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/suspend")
async def suspend_agent(payload: dict):
    """
    Kill Switch endpoint called by Datadog Monitors.
    """
    logger.critical("KILL SWITCH ACTIVATED via Webhook!")
    logger.critical(f"Reason: {payload}")
    global SUSPENDED
    SUSPENDED = True
    return {"status": "Agent Suspended"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
