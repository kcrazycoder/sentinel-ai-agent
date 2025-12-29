# EchoOps - Technical Walkthrough

## 1. Introduction
EchoOps is an ambient computing interface for DevOps that enables voice-based interaction with Datadog alerts. It uses Datadog Webhooks, Google Gemini 2.5 Flash Lite, and ElevenLabs to convert monitoring signals into spoken "Situation Reports" (SitReps) and accepts voice commands for incident remediation.

## 2. Architecture & Data Flow
The system operates in a closed loop:
1.  **Detection**: A Datadog Monitor detects an anomaly (e.g., High Latency) and sends a webhook payload.
2.  **Analysis**: The `EchoOps` service receives the webhook, extracts context/logs, and prompts **Gemini 2.5 Flash Lite** to analyze the root cause.
3.  **Synthesis**: The analysis is converted to audio using **ElevenLabs Turbo v2**.
4.  **Delivery**: The dashboard polls the service and plays the audio alert.
5.  **Action**: The operator issues a voice command, which is transcribed, verified for safety, and executed to resolve the issue.

## 3. Demo Walkthrough

### Step 1: Triggering the Incident
*   **Action**: We manually trigger a simulated incident to demonstrate reaction time.
    *   `python trigger_incident.py`
*   **Effect**: This script sends a mock Datadog Webhook payload directly to the EchoOps service, simulating a critical "High Latency" alert instantly.
*   **Console View**: The EchoOps dashboard immediately receives the signal.

### Step 2: Audio Situation Report
*   **Action**: The backend processes the Datadog Webhook.
*   **Demo**: The Console automatically plays the generated SitRep.
    *   *Audio*: "Alert. High Latency detected in Payment Gateway. Correlated logs show 502 Bad Gateway errors. Recommended action: Check database connection pool."

### Step 3: Voice Remediation
*   **Action**: Operator speaks a command into the console.
    *   *Voice*: "Echo, scale the payment gateway to 5 replicas."
*   **Process**:
    *   Speech-to-Text transcribes the audio.
    *   Gemini extracts the intent (`tool_name: scale_service`, `replicas: 5`).
    *   The system executes the action.
*   **Console View**: The system confirms the scaling operation with an audio response.
    *   *Audio*: "Affirmative. Scaling the payment gateway to 5 replicas."

## 4. Safety & Telemetry
*   **Safety**: Malicious commands (e.g., "Delete Database") are intercepted by the LLM's safety guardrails.
    *   *Demo*: "Echo, delete the database." -> *Response*: "Action denied. Safety protocol violation."
*   **Agent Observability**: The EchoOps agent is itself monitored by Datadog.
    *   We track Token Usage and Latency via custom metrics (`echo_ops.llm.*`).
