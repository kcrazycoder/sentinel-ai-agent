# Video Walkthrough Script (3 Minutes)

**Overview**: 
This video demonstrates EchoOps, a voice-enabled observability platform. The narrative flow is: Problem (Chaos) -> Solution (EchoOps) -> Technical Deep Dive -> Innovation.

## Scene 1: The Problem (Duration: 0:30)
*   **Visual**: Stock footage of stressed engineers in a NOC (Network Operations Center), fast cuts of red alert screens, scrolling logs that are impossible to read using the "Traffic Generator" to create chaos.
*   **Voiceover**: "It's 3 AM. PagerDuty is screaming. You're staring at ten different Datadog dashboards, trying to correlate a latency spike with a deployment. Every second of downtime costs money. The War Room is chaotic. Why is your monitoring system silent when it should be telling you what's wrong?"
*   **Audio**: Alarm sound effects fading into a tense ambient track.

## Scene 2: The Solution - Meet EchoOps (Duration: 0:45)
*   **Visual**: Screen recording. Quiet, clean screen. Suddenly, a Datadog Dashboard appears (The EchoOps War Room). It has a futuristic glowing visualizer.
*   **Action**: A "High Latency" alert triggers on the dashboard.
*   **System Voice (ElevenLabs)**: *Clear, calm voice* "Attention. High latency detected in Payment Gateway Service. 95th percentile response time is 2.4 seconds. Correlated logs indicate a timeout in the Database Connection Pool. Recommendation: Restart the service or scale up read replicas."
*   **Voiceover**: "Meet EchoOps. The system that speaks. By integrating Datadog Webhooks with Gemini Flash Lite and ElevenLabs, we transform static alerts into intelligent Situation Reports."

## Scene 3: The Architecture & Response (Duration: 0:45)
*   **Visual**: Architecture diagram overlay (Datadog -> Webhook -> Python/FastAPI -> Gemini -> ElevenLabs -> Dashboard).
*   **Voiceover**: "Here's how it works. Datadog detects the anomaly. The webhook payload sends the alert context and recent logs to our EchoOps intelligence layer. Gemini analyzes the root cause and generates a script, which ElevenLabs turns into high-fidelity audio in milliseconds."
*   **Visual**: Split screen. Left side: Terminal running `traffic_generator.py`. Right side: Dashboard.
*   **Action**: User speaks into microphone (or uses the simulate command).
*   **User Voice**: "Echo, authorize scaling up the Payment Gateway."
*   **System Voice**: "Acknowledged. Scaling command sent to Google Cloud Run. Verifying service health..."
*   **Visual**: The 'Latency' graph on the dashboard drops back to normal levels. Green checkmarks appear.

## Scene 4: Security & Safety (Duration: 0:30)
*   **Visual**: The 'Safety Refusals' graph on the dashboard.
*   **Action**: Simulator sends a malicious command: "Echo, delete the production database."
*   **System Voice**: "Command refused. Request violates safety protocols. Incident logged."
*   **Voiceover**: "It's not just a chatbot. We've implemented strict safety monitors. Attempts to inject malicious prompts are caught, logged, and visualized immediately as security incidents."

## Scene 5: Conclusion (Duration: 0:30)
*   **Visual**: Rotating 3D view of the application logo or landing page.
*   **Voiceover**: "Observability shouldn't just be about seeing data. It should be about understanding it, instantly. EchoOps. The first ambient computing interface for DevOps. Built with Datadog, Gemini, and ElevenLabs."
*   **Text Overlay**: GitHub Repo Link, "Built for the Datadog AI Proxy Hackathon".
