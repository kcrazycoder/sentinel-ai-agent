import logging
import os
import json
import time
import asyncio
import random
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
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

@app.on_event("startup")
async def startup_event():
    """Ensure status.json exists on startup to prevent 404s."""
    status_path = os.path.join("static", "status.json")
    if not os.path.exists(status_path):
        with open(status_path, "w") as f:
            json.dump({
                "text": "Waiting for Signal...",
                "audio_available": False,
                "timestamp": str(time.time())
            }, f)
        logger.info("Created default status.json")

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
async def datadog_webhook(payload: dict, background_tasks: BackgroundTasks):
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
            
            # 4. Generate Voice (Enabled)
            from voice_handler import FEMALE_VOICE_ID
            voice_provider = os.getenv("SITREPS_VOICE_PROVIDER", os.getenv("VOICE_PROVIDER", "elevenlabs"))
            background_tasks.add_task(generate_command_audio, sitrep_script, FEMALE_VOICE_ID, voice_provider)

            
            # Write Initial Status (Before audio is ready)
            import json
            status_data = {
                "text": sitrep_script, # Display text immediately
                "audio_available": False, 
                "timestamp": str(payload.get("timestamp", "now"))
            }
            with open(os.path.join("static", "status.json"), "w") as f:
                json.dump(status_data, f)

            return {
                "status": "processed", 
                "sitrep": sitrep_script,
                "audio_queued": True
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



from voice_handler import DEFAULT_VOICE_ID

def generate_command_audio(text: str, voice_id: str = DEFAULT_VOICE_ID, provider: str = None):
    """
    Background task to generate audio and update status.json
    """
    logger.info(f"Starting background audio generation for: {text[:30]}... (Voice: {voice_id}, Provider: {provider})")
    try:
        audio_bytes = generate_voice(text, voice_id, provider)
        if audio_bytes:
            audio_filename = f"response_{int(time.time())}.wav"
            file_path = os.path.join("static", audio_filename)
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
            
            # Update status.json so frontend picks it up
            # We need to be careful not to overwrite a *newer* status, but for this single-stream demo it's acceptable.
            # To be safer, we read, check timestamp, then write? 
            # Or just write a specific "audio_update" status.
            
            # Simplest approach for hackathon: Update global status with audio link.
            status_data = {
                "text": text, # Re-iterate text
                "audio_available": True,
                "audio_url": f"/static/{audio_filename}",
                "timestamp": str(time.time()) # Update timestamp to trigger frontend fetch
            }
            with open(os.path.join("static", "status.json"), "w") as f:
                json.dump(status_data, f)
            logger.info(f"Audio ready: {audio_filename}")
        else:
             logger.warning("Background audio generation failed (no bytes returned).")
    except Exception as e:
        logger.error(f"Background audio task failed: {e}")

# --- Chaos Engineering ---
CHAOS_MODE = False

@app.post("/chaos/start")
async def start_chaos():
    global CHAOS_MODE
    CHAOS_MODE = True
    logger.warning("CHAOS MODE ACTIVATED: Latency injection enabled.")
    return {"status": "chaos_started", "latency_injection": "enabled"}

@app.post("/chaos/stop")
async def stop_chaos():
    global CHAOS_MODE
    CHAOS_MODE = False
    logger.info("CHAOS MODE DEACTIVATED: Latency injection disabled.")
    return {"status": "chaos_stopped"}

@app.post("/command")
async def process_voice_command(cmd: VoiceCommand, background_tasks: BackgroundTasks):
    """
    Process a voice transcript, validate intent, and execute tool.
    Returns text immediately; queues audio generation.
    """
    global CHAOS_MODE
    start_time = time.time()
    
    # 0. Chaos Injection
    start_time = time.time()
    
    if CHAOS_MODE:
        # Simulate high latency (2.5s - 4.0s) to trip Datadog monitors
        delay = random.uniform(2.5, 4.0)
        logger.warning(f"Chaos Mode: Injecting {delay:.2f}s latency...")
        await asyncio.sleep(delay)

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
            tool_name = intent_dict.get("tool_name")
            
            if tool_name == "refusal":
                statsd.increment('echo_ops.intent.refusal', tags=[
                    f"user_id:{cmd.user_id}",
                    "service:sentinel-ai",
                    "reason:blocked_by_ai" # Generic tag to avoid high cardinality if reason is free text
                ])
            elif tool_name:
                 # Track successful tool identification
                statsd.increment('echo_ops.intent.tool_usage', tags=[
                    f"user_id:{cmd.user_id}",
                    "service:sentinel-ai",
                    f"tool_name:{tool_name}"
                ])
                
            intent_json = cleaned_intent # Keep original string for return if needed, or re-dump

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse intent JSON: {intent_str}")
            intent_dict = {"error": "parsing_failed", "raw": intent_str}

        # Metric Instrumentation: Latency SLO
        duration = time.time() - start_time
        statsd.gauge('echo_ops.latency', duration, tags=["service:sentinel-ai"])
        
        # "Satisfactory" metric for SLO (1 if <1s, 0 if >1s)
        is_satisfactory = 1 if duration < 1.0 else 0
        statsd.increment('echo_ops.latency.satisfactory', value=is_satisfactory, tags=["service:sentinel-ai"])
        # Total count for accurate SLO denominator (Total = Satisfactory + Unsatisfactory)
        statsd.increment('echo_ops.latency.total', tags=["service:sentinel-ai"])

        # Construct Feedback Message (and Audio Script)
        message = ""
        tool_name = intent_dict.get("tool_name") # Re-get tool_name in case of parsing error
        
        if tool_name == "refusal":
            # Robust extraction of reason
            reason = "Unknown reason"
            args = intent_dict.get("arguments", {})
            if isinstance(args, dict):
                reason = args.get("reason", intent_dict.get("reason", "Unknown reason"))
            elif isinstance(args, str):
                reason = args
            message = f"Command Refused: {reason}"
            audio_script = f"Action denied. {reason}"
        elif tool_name:
            args_str = ", ".join([f"{k}={v}" for k, v in intent_dict.get("arguments", {}).items()])
            message = f"Executed {tool_name}"
            if args_str:
                message += f" ({args_str})"
            audio_script = f"Executing {tool_name}. {args_str}." # Simple confirmation
        else:
            message = "Command Processed (No specific tool identified)"
            audio_script = "Command processed."

        # Update Frontend Dashboard IMMEDIATE (Text Only)
        try:
            status_text = f"COMMAND RECEIVED: {cmd.transcript}\nACTION: {tool_name or 'UNKNOWN'}\nRESULT: {message}"
            status_data = {
                "text": status_text,
                "audio_available": False, 
                "timestamp": str(time.time())
            }
            with open(os.path.join("static", "status.json"), "w") as f:
                json.dump(status_data, f)
        except Exception as e:
            logger.error(f"Failed to update dashboard status: {e}")

        # Queue Audio Generation
        voice_provider = os.getenv("COMMANDS_VOICE_PROVIDER", os.getenv("VOICE_PROVIDER", "elevenlabs"))
        background_tasks.add_task(generate_command_audio, audio_script, DEFAULT_VOICE_ID, voice_provider)

        # Return Immediate Response
        return {
            "status": "executed", 
            "intent": intent_dict,
            "message": message
        }

    except Exception as e:
        logger.error(f"Command Processing Failed: {e}")
        return {"status": "failed", "error": str(e)}

    finally:
        # 4. Telemetry: Token Usage & Cost
        try:
            # Estimation Fallback (SAFE)
            input_tokens = len(cmd.transcript) // 4
            output_tokens = 50 
            
            # Report to Datadog
            statsd.increment('echo_ops.llm.tokens.prompt', value=input_tokens, tags=["model:gemini-2.5-flash-lite"])
            statsd.increment('echo_ops.llm.tokens.completion', value=output_tokens, tags=["model:gemini-2.5-flash-lite"])
            statsd.increment('echo_ops.llm.tokens.total', value=input_tokens + output_tokens, tags=["model:gemini-2.5-flash-lite"])
            
            # Cost Estimation
            cost = (input_tokens / 1000 * 0.0001) + (output_tokens / 1000 * 0.0002)
            statsd.gauge('echo_ops.llm.cost', cost, tags=["model:gemini-2.5-flash-lite"])
            
            logger.info(f"Telemetry Sent: {input_tokens} in, {output_tokens} out, ${cost:.6f}")

        except Exception as tel_e:
            logger.warning(f"Telemetry Error: {tel_e}")

@app.get("/debug/audio")
def debug_audio():
    """
    Debug endpoint to verify voice generation configuration and execution.
    """
    try:
        # Check Config
        provider = os.getenv("VOICE_PROVIDER", "elevenlabs").lower().strip()
        google_key = os.getenv("GOOGLE_API_KEY", "").strip()
        eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        
        config_status = {
            "VOICE_PROVIDER": provider,
            "GOOGLE_API_KEY_PRESENT": bool(google_key),
            "ELEVENLABS_API_KEY_PRESENT": bool(eleven_key),
            "GOOGLE_API_KEY_LENGTH": len(google_key) if google_key else 0
        }

        # Attempt Generation
        logger.info(f"Debug Audio: Attempting generation with provider={provider}")
        start_time = time.time()
        audio_content = generate_voice("This is a test of the EchoOps audio system.")
        duration = time.time() - start_time
        
        result = {
            "config": config_status,
            "generation_attempt": {
                "success": bool(audio_content),
                "bytes": len(audio_content) if audio_content else 0,
                "duration_seconds": round(duration, 2)
            }
        }
        
        if not audio_content:
             result["error"] = "Generation failed. Check logs for details."
             
        return result
        
    except Exception as e:
        logger.error(f"Debug endpoint failed: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
