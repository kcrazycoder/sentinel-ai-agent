import requests
import time

try:
    print("Sending single Trigger request...")
    resp = requests.post("http://localhost:8000/chat", json={"message": "trigger", "user_id": "tester"})
    print(f"Response: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
