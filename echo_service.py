import logging
import os
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any

from dotenv import load_dotenv

# Trace everything!
from ddtrace import patch_all, tracer
patch_all()

from datadog import initialize, statsd

# Initialize Datadog (relies on DD_AGENT_HOST/DD_API_KEY env vars or defaults)
initialize()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser

# Import our Prompts and Handlers
from prompts import sitrep_prompt, intent_prompt
from voice_handler import generate_voice

# Load Env
load_dotenv()

# Configure Logging (Datadog Friendly)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("echo_ops")

app = FastAPI(title="EchoOps Service")

# Mount Static Files for the Dashboard Widget
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Gemini
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite", # Using Flash Lite as requested
        temperature=0.1,
        max_retries=2
    )
    logger.info("EchoOps Intelligence Layer (Gemini) Initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Gemini: {e}")
    llm = None

# --- Models ---
class DatadogWebhookPayload(BaseModel):
    id: Optional[str] = None
    event_title: Optional[str] = "Test Alert"
    event_type: Optional[str] = "string"
    body: Optional[str] = "Test Body"
    alert_query: Optional[str] = None

class VoiceCommand(BaseModel):
    transcript: str
    user_id: str

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "operational", "system": "EchoOps"}

@app.post("/webhook/datadog")
async def datadog_webhook(payload: dict):
    """
    Receives alerts from Datadog.
    1. Extracts context.
    2. Fetches dummy logs (Simulated for this hackathon demo).
    3. Generates SitRep via Gemini.
    4. Generates Audio via ElevenLabs.
    """
    span = tracer.current_span()
    if span:
        span.set_tag("event.type", "alert_ingest")
    
    logger.info(f"Received Alert Payload: {payload}")
    
    # 1. Extract Context
    # Handle different payload structures if necessary
    alert_title = payload.get("event_title", payload.get("title", "Unknown Alert"))
    alert_body = payload.get("body", payload.get("message", ""))
    
    # 2. Simulate Log Fetching (In a real app, we'd query the DD Log Search API here)
    simulated_logs = "TIMESTAMP=2024-12-22T10:00:01 ERROR Component=PaymentGateway Message='Connection Refused: 502 Bad Gateway'\nTIMESTAMP=2024-12-22T10:00:02 WARN Component=CheckoutService Message='Retrying transaction...'"
    
    if "latency" in str(alert_title).lower():
        simulated_logs += "\nTIMESTAMP=2024-12-22T10:00:05 ERROR Component=DB_Pool Message='Timeout waiting for connection'"

    logger.info("Context extracted. Analyzing with Gemini...")

    sitrep_script = "Analysis failed."
    audio_path = None

    # 3. Generate SitRep
    if llm:
        try:
            chain = sitrep_prompt | llm | StrOutputParser()
            sitrep_script = await chain.ainvoke({
                "alert_title": alert_title,
                "alert_query": payload.get("alert_query", "N/A"),
                "log_snippets": simulated_logs
            })
            
            logger.info(f"Generated SitRep: {sitrep_script}")
            
            # 4. Generate Voice
            audio_bytes = generate_voice(sitrep_script)
            audio_path = None
            
            if audio_bytes:
                # Save to static folder
                audio_filename = "latest_sitrep.mp3"
                file_path = os.path.join("static", audio_filename)
                with open(file_path, "wb") as f:
                    f.write(audio_bytes)
                audio_path = f"/static/{audio_filename}"
                logger.info(f"Audio saved to {file_path}")
            
            # Write Status for Frontend (Fallback Support)
            import json
            status_data = {
                "text": sitrep_script,
                "audio_available": audio_path is not None,
                "timestamp": str(payload.get("timestamp", "now"))
            }
            with open(os.path.join("static", "status.json"), "w") as f:
                json.dump(status_data, f)

            return {
                "status": "processed", 
                "sitrep": sitrep_script,
                "audio_url": audio_path
            }
            
        except Exception as e:
            logger.error(f"Processing Failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return {"status": "error", "message": "LLM not available"}

@app.post("/webhook/suspend")
async def suspend_webhook(request: Request):
    """
    Dummy endpoint to handle Cloud Run/Datadog suspension lifecycle hooks.
    """
    body = await request.body()
    logger.info(f"Suspend Webhook Received: {body.decode()}")
    return {"status": "suspended"}

@app.post("/command")
async def process_voice_command(cmd: VoiceCommand):
    """
    Process a voice transcript, validate intent, and execute tool.
    """
    logger.info(f"Processing Command: {cmd.transcript}")
    
    if not llm:
        raise HTTPException(status_code=503, detail="LLM Offline")

    # Intent Classification
    try:
        chain = intent_prompt | llm | StrOutputParser()
        intent_str = await chain.ainvoke({"transcript": cmd.transcript})
        
        # Robustly extract JSON from potential conversational output
        try:
            # Find the first opening brace and the last closing brace
            start_idx = intent_str.find('{')
            end_idx = intent_str.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                cleaned_intent = intent_str[start_idx : end_idx + 1]
            else:
                cleaned_intent = intent_str.strip() # Fallback to original behavior
                
            intent_dict = json.loads(cleaned_intent)
            # Log as structured JSON for Datadog
            logger.info(json.dumps({
                "event": "intent_analysis",
                "transcript": cmd.transcript,
                "intent": intent_dict
            }))
            
            # Metric Instrumentation: Track Refusals
            if intent_dict.get("intent", {}).get("tool_name") == "refusal":
                statsd.increment('echo_ops.intent.refusal', tags=[
                    f"user_id:{cmd.user_id}",
                    "service:sentinel-ai",
                    "reason:blocked_by_ai" # Generic tag to avoid high cardinality if reason is free text
                ])
            elif intent_dict.get("intent", {}).get("tool_name"):
                 # Track successful tool identification
                tool_name = intent_dict.get("intent", {}).get("tool_name")
                statsd.increment('echo_ops.intent.tool_usage', tags=[
                    f"user_id:{cmd.user_id}",
                    "service:sentinel-ai",
                    f"tool_name:{tool_name}"
                ])
                
            intent_json = cleaned_intent # Keep original string for return if needed, or re-dump
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse intent JSON: {intent_str}")
            intent_dict = {"error": "parsing_failed", "raw": intent_str}

        # Mock Execution
        return {"status": "executed", "intent": intent_dict}

    except Exception as e:
        logger.error(f"Command Processing Failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        # 4. Telemetry: Token Usage & Cost
        try:
            # Note: actual usage metadata depends on the specific LangChain integration version and response structure.
            # providing a robust fallback if usage_metadata is missing.
            usage = None
            if hasattr(chain, "last_response") and hasattr(chain.last_response, "usage_metadata"):
                 usage = chain.last_response.usage_metadata
            
            # Since we are using a simple chain | invoke, getting the raw response object to extract metadata 
            # might require a different approach (e.g. callbacks). 
            # For this simplified agent, we will estimate or Mock if we can't easily grab it without refactoring the chain.
            # HOWEVER, ChatGoogleGenerativeAI responses usually contain usage_metadata in the raw output.
            # Let's try to get it if we can, otherwise we will estimate based on string length (1 token ~= 4 chars)
            
            # Estimation Fallback (SAFE)
            input_tokens = len(cmd.transcript) // 4
            output_tokens = 50 # Avg for intent JSON
            
            # Report to Datadog
            statsd.increment('echo_ops.llm.tokens.prompt', value=input_tokens, tags=["model:gemini-2.5-flash-lite"])
            statsd.increment('echo_ops.llm.tokens.completion', value=output_tokens, tags=["model:gemini-2.5-flash-lite"])
            statsd.increment('echo_ops.llm.tokens.total', value=input_tokens + output_tokens, tags=["model:gemini-2.5-flash-lite"])
            
            # Cost Estimation (Hypothetical pricing for Flash Lite: $0.0001 per 1k input, $0.0002 per 1k output)
            cost = (input_tokens / 1000 * 0.0001) + (output_tokens / 1000 * 0.0002)
            statsd.gauge('echo_ops.llm.cost', cost, tags=["model:gemini-2.5-flash-lite"])
            
            logger.info(f"Telemetry Sent: {input_tokens} in, {output_tokens} out, ${cost:.6f}")

        except Exception as tel_e:
            logger.warning(f"Telemetry Error: {tel_e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
