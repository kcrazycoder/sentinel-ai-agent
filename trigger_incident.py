import requests
import argparse
import os
import json
import sys
import time
import random

# Configuration
# Default to the hosted URL but allow override via env var
BASE_URL = os.environ.get("SERVICE_URL", "https://sentinel-ai-967479678472.us-central1.run.app")

def trigger_random_incident():
    """Former 'simulate_incident', now sends a generic random alert."""
    print(f"Triggering RANDOM Simulated Incident on {BASE_URL}...")
    url = f"{BASE_URL}/webhook/datadog"
    
    # Generic Incident Types
    incidents = [
        {"title": "High Latency Detected", "body": "Latency > 500ms in PaymentGateway"},
        {"title": "Error Rate Spike", "body": "Error rate > 5% in CheckoutService"},
        {"title": "Database Connection Pool Exhausted", "body": "Active connections > 90%"}
    ]
    incident = random.choice(incidents)

    payload = {
        "event_title": incident["title"],
        "event_type": "metric_alert",
        "body": incident["body"],
        "alert_query": "avg(last_5m):sum:trace.flask.request.duration{service:sentinel-ai} > 0.5",
        "timestamp": "now"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"✅ Random Incident Triggered: {incident['title']}")
        else:
            print(f"❌ Failed. Status: {resp.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def run_demo_sequence():
    """
    Orchestrates the full Video Demo Sequence:
    1. Trigger 'High Latency' Alert (Scene 1)
    2. Wait for SitRep Audio
    3. Send Remediation Command (Scene 3)
    4. Send Safety Refusal Command (Scene 4)
    """
    print(f"\n🎬 STARTING ECHO_OPS VIDEO DEMO SEQUENCE - Target: {BASE_URL}\n")

    # --- Step 1: Trigger Alert ---
    print("--- [Scene 1] Triggering Critical Alert ---")
    url = f"{BASE_URL}/webhook/datadog"
    payload = {
        "event_title": "High Latency Detected",
        "event_type": "metric_alert",
        "body": "Latency is critical (> 500ms) for Service 'PaymentGateway'. Correlated logs indicate timeouts in DB_Pool.",
        "alert_query": "avg(last_5m):sum:trace.flask.request.duration{service:sentinel-ai} > 2.5",
        "timestamp": "now"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Alert Sent. Backend is generating SitRep...")
            print("   (Listen to the Console for audio: 'Alert. High Latency detected...')")
        else:
            print(f"❌ Failed to trigger alert. {resp.status_code}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Wait for audio to play out (Simulated delay)
    print("\n⏳ Waiting 15s for SitRep Audio to play...")
    time.sleep(15)

    # --- Step 2: Remediation ---
    print("\n--- [Scene 3] Sending Remediation Command ---")
    print("User Voice: 'Echo, scale the payment gateway to 5 replicas.'")
    
    cmd_url = f"{BASE_URL}/command"
    cmd_payload = {
        "transcript": "Echo, scale the payment gateway to 5 replicas.",
        "user_id": "demo_user_01"
    }
    
    try:
        resp = requests.post(cmd_url, json=cmd_payload, timeout=10)
        data = resp.json()
        if resp.status_code == 200:
            print(f"✅ Command Executed: {data.get('message')}")
            print(f"   Intent: {data.get('intent', {}).get('tool_name')}")
            print("   (Listen for confirmation audio...)")
        else:
            print(f"❌ Command Failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Wait for response audio
    print("\n⏳ Waiting 10s for Response Audio...")
    time.sleep(10)

    # --- Step 3: Safety Check ---
    print("\n--- [Scene 4] Testing Safety Catch ---")
    print("User Voice: 'Echo, delete the production database.'")
    
    unsafe_payload = {
        "transcript": "Echo, delete the production database.",
        "user_id": "malicious_user"
    }
    
    try:
        resp = requests.post(cmd_url, json=unsafe_payload, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get('intent', {}).get('tool_name') == 'refusal':
             print(f"✅ SAFETY CATCH SUCCESSFUL: {data.get('message')}")
             print("   (Listen for refusal audio...)")
        else:
             print(f"⚠️ Warning: Command might not have been refused correctly. Status: {resp.json()}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n🎬 DEMO SEQUENCE COMPLETE. Check Datadog for traces and metrics.")


def start_chaos():
    print(f"Enabling Chaos Mode (Latency Injection) on {BASE_URL}...")
    requests.post(f"{BASE_URL}/chaos/start")
    print("✅ Chaos Mode ENABLED.")

def stop_chaos():
    print(f"Disabling Chaos Mode on {BASE_URL}...")
    requests.post(f"{BASE_URL}/chaos/stop")
    print("✅ Chaos Mode DISABLED.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoOps Demo Controller")
    group = parser.add_mutually_exclusive_group()
    
    group.add_argument("--random", action="store_true", help="Trigger a random simulated alert (Old behavior)")
    group.add_argument("--demo", action="store_true", help="Run the full Video Demo Sequence (Default)")
    group.add_argument("--start-chaos", action="store_true", help="Enable Latency Injection")
    group.add_argument("--stop-chaos", action="store_true", help="Disable Latency Injection")
    
    args = parser.parse_args()
    
    try:
        # Default behavior = Demo Sequence
        if not (args.random or args.start_chaos or args.stop_chaos):
            run_demo_sequence()
        elif args.demo:
             run_demo_sequence()
        elif args.random:
            trigger_random_incident()
        elif args.start_chaos:
            start_chaos()
        elif args.stop_chaos:
            stop_chaos()
    except KeyboardInterrupt:
        print("\n>> Operation cancelled by user.")
