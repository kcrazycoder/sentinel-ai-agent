import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any

from dotenv import load_dotenv

# Trace everything!
from ddtrace import patch_all, tracer
patch_all()

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
        model="gemini-1.5-pro", # Using Pro for better reasoning on logs
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
            if audio_bytes:
                # Save to static folder
                audio_filename = "latest_sitrep.mp3"
                file_path = os.path.join("static", audio_filename)
                with open(file_path, "wb") as f:
                    f.write(audio_bytes)
                audio_path = f"/static/{audio_filename}"
                logger.info(f"Audio saved to {file_path}")
            
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
        intent_json = await chain.ainvoke({"transcript": cmd.transcript})
        
        logger.info(f"Intent Analysis: {intent_json}")
        
        # Mock Execution
        return {"status": "executed", "intent": intent_json}
        
    except Exception as e:
        logger.error(f"Command Processing Failed: {e}")
        return {"status": "failed", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
