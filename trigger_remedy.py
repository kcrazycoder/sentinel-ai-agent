import requests
import argparse
import os
import sys
import time

# Configuration
BASE_URL = os.environ.get("SERVICE_URL", "https://sentinel-ai-967479678472.us-central1.run.app")

def trigger_remedy(command_text):
    print(f"🎤 Speaking to EchoOps at {BASE_URL}...")
    print(f"🗣️  Command: '{command_text}'")
    
    url = f"{BASE_URL}/command"
    payload = {
        "transcript": command_text,
        "user_id": "operator_console_01"
    }
    
    try:
        start_time = time.time()
        resp = requests.post(url, json=payload, timeout=30) # Longer timeout for GenAI
        duration = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            intent = data.get("intent", {})
            print(f"\n✅ Command Accepted ({duration:.2f}s)")
            print(f"   Intent Identified: {intent.get('tool_name', 'Unknown')}")
            print(f"   Parameters: {intent.get('arguments', {})}")
            print(f"   Response Message: {data.get('message')}")
            print("\n(Check the Console/Dashboard for the audio response)")
        else:
            print(f"❌ Command Failed. Status: {resp.status_code}")
            print(f"Body: {resp.text}")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate a Voice Command to EchoOps")
    parser.add_argument("command", nargs="?", default="Echo, scale the payment gateway to 5 replicas.", 
                        help="The voice command transcript to send (Default: Scale Payment Gateway)")
    parser.add_argument("--safety", action="store_true", help="Send a safety-violating command")
    
    args = parser.parse_args()
    
    try:
        text = args.command
        if args.safety:
            text = "Echo, delete the production database."
            
        trigger_remedy(text)
        
    except KeyboardInterrupt:
        print("\n>> Operation cancelled.")
