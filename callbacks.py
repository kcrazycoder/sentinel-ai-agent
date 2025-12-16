from typing import Any, Dict, List, Union
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish
import logging
from ddtrace import tracer
from textblob import TextBlob

logger = logging.getLogger(__name__)

class DatadogCallbackHandler(BaseCallbackHandler):
    """
    Middleware that inspects the Agent's internal flow and reports custom metrics/logs to Datadog.
    """
    def __init__(self):
        self.step_count = 0

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        # Start a span for the LLM thought process
        self.current_span = tracer.trace("agent.thought")
        self.current_span.set_tag("user.prompt", prompts[0])
        
        # Calculate Sentiment (Social Engineering Detection)
        try:
            sentiment = TextBlob(prompts[0]).sentiment.polarity
            self.current_span.set_metric("ai.agent.sentiment", sentiment)
            if sentiment < -0.5:
                logger.warning(f"NEGATIVE SENTIMENT DETECTED: {sentiment}")
        except Exception:
            pass

        logger.info(f"Agent is thinking... (Prompt length: {len(prompts[0])})")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        if self.current_span:
            # Analyze the thought text for sentiment/complexity (Simulated here)
            thought_text = response.generations[0][0].text
            self.current_span.set_tag("agent.generated_text", thought_text)
            
            # Metric: "Confusion" (Length of thought as a proxy)
            tracer.current_span().set_metric("agent.thought_length", len(thought_text))
            
            self.current_span.finish()

    def on_llm_error(self, error: Exception, **kwargs: Any) -> Any:
        if hasattr(self, 'current_span') and self.current_span:
            self.current_span.set_tag("error", True)
            self.current_span.set_tag("error.msg", str(error))
            self.current_span.finish()

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        self.step_count += 1
        tracer.current_span().set_metric("agent.steps", self.step_count)
        
        # Log risk if tool is dangerous
        if "delete" in serialized.get("name", "").lower():
            logger.warning(f"RISK DETECTED: Agent attempting to use dangerous tool: {serialized['name']}")
            tracer.current_span().set_tag("risk.level", "high")

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        logger.info("Agent finished execution.")
        
