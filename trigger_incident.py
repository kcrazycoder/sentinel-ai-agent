
import requests
import json
import time

# Configuration
WEBHOOK_URL = "https://sentinel-ai-967479678472.us-central1.run.app/webhook/datadog"

# The "Mock" Datadog Alert Payload
# This matches the structure expected by echo_service.py
payload = {
    "event_title": "High Latency in PaymentGateway",
    "body": "Latency > 500ms on /process_payment. 95th percentile is 2.4s.",
    "link": "https://app.datadoghq.com/dashboard/xyz",
    "timestamp": int(time.time()),
    "tags": ["env:production", "service:payment-gateway", "version:v2.4"]
}

def trigger_incident():
    print(f"Triggering Incident at {WEBHOOK_URL}...")
    try:
        response = requests.post(
            WEBHOOK_URL, 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Incident Triggered! Check your Datadog Dashboard (Voice Console).")
    except Exception as e:
        print(f"Failed to trigger incident: {e}")

if __name__ == "__main__":
    trigger_incident()
