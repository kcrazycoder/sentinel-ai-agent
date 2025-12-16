# SentinelAI - Setup & Run Instructions

## 1. Environment Setup

The automatic installation encountered issues building `ddtrace`. Please try installing manually in your preferred terminal (Git Bash):

```bash
# Activate virtual environment
source venv/Scripts/activate

# Install dependencies (ensure C++ Build Tools or pre-built wheels are available)
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

*Note: If `ddtrace` fails to compile, you may need to install the Microsoft C++ Build Tools or use a compatible binary wheel.*

## 2. Configuration
Create a `.env` file with your credentials:
```env
# Google Vertex AI
GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json"
project_id="your-project-id"

# Datadog
DD_API_KEY="your_api_key"
DD_APP_KEY="your_app_key"
DD_SITE="datadoghq.com"
DD_SERVICE="sentinel-ai-agent"
DD_ENV="hackathon-dev"
DD_LOGS_INJECTION=true
```

## 3. Running the Server
Since `patch_all()` is already included in `main.py`, you don't need the `ddtrace-run` wrapper (which can be flaky on Windows).

Run directly with Python:
```bash
python main.py
```
Or with Uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 4. Simulating Traffic
In a separate terminal:
```bash
python traffic_generator.py
```

## 5. View in Datadog
- **APM:** Go to APM > Traces to see the agent's Chain of Thought.
- **Metrics:** Check `agent.thought_length` and custom risk tags.
- **Logs:** Filter by `service:sentinel-ai-agent`.

## 6. Submission Deliverables & Export
For the Hackathon submission, this repository includes:

- **Instrumented App**: `agent.py` (LangChain + Gemini) & `callbacks.py` (Datadog).
- **Datadog Config**: Import `datadog_export.json` to automatically create the Monitors and Dashboard widgets.
- **License**: MIT License included in `LICENSE` file.
- **Traffic Generator**: `traffic_generator.py` demonstrates the detection rules in action.

### Deployment Notes
To host this application publicly:
1.  Deploy to **Google Cloud Run** or **Render**.
2.  Set the environment variables defined in `.env` in your cloud provider's dashboard.
3.  The application listens on `$PORT` (default 8000).
