
import requests
import json
import time
import random

# Configuration
WEBHOOK_URL = "https://sentinel-ai-967479678472.us-central1.run.app/webhook/datadog"

# Scenarios
scenarios = [
    {
        "event_title": "High Latency in PaymentGateway",
        "body": "Latency > 500ms on /process_payment. 95th percentile is 2.4s.",
        "tags": ["env:production", "service:payment-gateway", "version:v2.4"],
        "alert_query": "avg(last_5m):avg:trace.http.request.duration{service:payment-gateway} > 0.5"
    },
    {
        "event_title": "Error Rate Spike in CheckoutService",
        "body": "5xx Error Rate > 5%. 502 Bad Gateway errors detected upstream.",
        "tags": ["env:production", "service:checkout-service", "team:checkout"],
        "alert_query": "sum(last_5m):sum:trace.http.request.errors{service:checkout-service}.as_count() > 10"
    },
    {
        "event_title": "Security: SQL Injection Attempt Detected",
        "body": "WAF blocked suspicious request pattern: 'DROP TABLE users'. IP: 203.0.113.42",
        "tags": ["env:production", "service:frontend", "security:high"],
        "alert_query": "sum(last_5m):sum:security.waf.blocked{rule:sqli}.as_count() > 0"
    }
]

def trigger_incident():
    # Pick a random scenario
    scenario = random.choice(scenarios)
    
    # Add dynamic timestamp
    payload = scenario.copy()
    payload["timestamp"] = int(time.time())
    payload["link"] = "https://app.datadoghq.com/dashboard/xyz"

    print(f"Triggering Incident: {payload['event_title']}")
    print(f"Url: {WEBHOOK_URL}")
    
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
