import requests
import argparse
import os
import json
import sys

# Configuration
# Default to the hosted URL but allow override via env var, similar to traffic_generator.py
BASE_URL = os.environ.get("SERVICE_URL", "https://sentinel-ai-967479678472.us-central1.run.app")

def simulate_incident():
    print(f"Triggering Simulated Incident on {BASE_URL}...")
    url = f"{BASE_URL}/webhook/datadog"
    
    # Payload matching what echo_service.py expects
    payload = {
        "event_title": "High Latency Detected",
        "event_type": "metric_alert",
        "body": "Latency is critical (> 500ms) for Service 'PaymentGateway'.",
        "alert_query": "avg(last_5m):sum:trace.flask.request.duration{service:sentinel-ai} > 0.5",
        "timestamp": "now"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Incident Triggered Successfully.")
            print(f"Response: {resp.json()}")
        else:
            print(f"❌ Failed to trigger incident. Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def start_chaos():
    print(f"Enabling Chaos Mode (Latency Injection) on {BASE_URL}...")
    url = f"{BASE_URL}/chaos/start"
    try:
        resp = requests.post(url, timeout=10)
        if resp.status_code == 200:
            print("✅ Chaos Mode ENABLED.")
            print("The service will now inject artificial latency (2.5s - 4.0s) into commands.")
        else:
            print(f"❌ Failed to enable chaos. Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def stop_chaos():
    print(f"Disabling Chaos Mode on {BASE_URL}...")
    url = f"{BASE_URL}/chaos/stop"
    try:
        resp = requests.post(url, timeout=10)
        if resp.status_code == 200:
            print("✅ Chaos Mode DISABLED.")
            print("Service latency returned to normal.")
        else:
            print(f"❌ Failed to disable chaos. Status: {resp.status_code}")
            print(f"Body: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger Incidents or Control Chaos Mode for EchoOps")
    group = parser.add_mutually_exclusive_group()
    
    group.add_argument("--simulate", action="store_true", help="Simulate a Datadog Alert Webhook (Default)")
    group.add_argument("--start-chaos", action="store_true", help="Enable Latency Injection on the server")
    group.add_argument("--stop-chaos", action="store_true", help="Disable Latency Injection on the server")
    
    args = parser.parse_args()
    
    try:
        # Default behavior if no args provided
        if not (args.start_chaos or args.stop_chaos):
            # Implicitly --simulate
            simulate_incident()
        elif args.start_chaos:
            start_chaos()
        elif args.stop_chaos:
            stop_chaos()
    except KeyboardInterrupt:
        print("\n>> Operation cancelled by user.")
