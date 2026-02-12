"""LLM client with Guardrails (v1.7.0)."""
import json
import asyncio
import random
from typing import Optional, Literal, List
import httpx
from pydantic import BaseModel, Field, ValidationError

from logging_setup import get_logger
from settings import Settings
from llm_monitor import LLMMonitor, BudgetExceededError, CircuitBreaker

logger = get_logger("pipeline.llm")


class LLMResponse(BaseModel):
    """Strict output schema for LLM classification."""
    event_type: Literal["accident", "outage", "repair", "other"]
    relevance: float = Field(ge=0.0, le=1.0)
    urgency: int = Field(ge=1, le=5)
    object: Literal["water", "heat", "industrial", "unknown"]
    why: str
    action: Literal["call", "watch", "ignore"]


class LLMClient:
    """Robust LLM Client with Guardrails (Budget + Circuit Breaker)."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        # Strict "Free Models Only" policy by default
        self.primary_model = "google/gemini-2.0-flash-exp:free"
        self.fallback_models = [
            "meta-llama/llama-3.2-11b-vision-instruct:free",
            "microsoft/phi-3-medium-128k-instruct:free"
        ]
        
        # Current state
        self.active_model = self.primary_model
        
    async def analyze(
        self,
        title: str,
        text: str,
        region: Optional[str] = None,
        source: str = "",
        trace_id: str = ""
    ) -> tuple[Optional[LLMResponse], Optional[str], Optional[str]]:
        """
        Analyze news article with Guardrails and Retries.
        """
        # 1. Budget Guardrail
        try:
            await LLMMonitor.check_budget()
        except BudgetExceededError as e:
            logger.warning("llm_budget_exceeded", trace_id=trace_id, error=str(e))
            return None, None, "BUDGET_EXCEEDED"
            
        # 2. Circuit Breaker Guardrail
        if CircuitBreaker.is_open():
            logger.warning("llm_circuit_open", trace_id=trace_id)
            return None, None, "CIRCUIT_OPEN"

        original_prompt = self._build_prompt(title, text, region, source)
        
        # Try primary model, then fallbacks
        models_to_try = [self.active_model] + [m for m in self.fallback_models if m != self.active_model]
        
        last_error = None
        
        for model in models_to_try:
            self.active_model = model
            
            # Retry loop for this model (primarily for JSON errors)
            # limit 2 attempts as requested
            for attempt in range(2):
                current_prompt = original_prompt
                
                # On retry, emphasize JSON requirement
                if attempt > 0:
                    current_prompt += "\n\nSYSTEM_NOTE: Previous response was invalid JSON. RETURN ONLY RAW JSON. NO MARKDOWN."
                
                response, raw, error_code = await self._call_provider(model, current_prompt, trace_id)
                
                if response:
                    return response, raw, None
                
                # If JSON error, we can retry with the same model
                if error_code == "LLM_INVALID_JSON":
                    last_error = error_code
                    logger.warning("llm_json_retry", trace_id=trace_id, model=model, attempt=attempt+1)
                    continue
                
                # If network/rate limit error, stop retrying this model and switch to next model
                last_error = error_code
                break
            
            # If we reached here, the model failed (either retries exhausted or fatal error)
            # If rate limited, we definitely want to try next model
            if last_error in ("LLM_RATE_LIMIT", "LLM_TIMEOUT", "LLM_API_ERROR"):
                logger.info("llm_fallback_switch", trace_id=trace_id, from_model=model, reason=last_error)
                continue
                
            # If it was a persistent JSON error even after retry, we might want to try another model too?
            # User requirement: "Retry at invalid JSON (2 attempts max)" - likely implies per item.
            # If one model fails JSON 2 times, maybe it's too stupid. Let's try fallback.
            if last_error == "LLM_INVALID_JSON":
                 logger.info("llm_fallback_switch_json", trace_id=trace_id, from_model=model)
                 continue
            
        return None, None, last_error

    async def _call_provider(
        self, 
        model: str, 
        prompt: str, 
        trace_id: str
    ) -> tuple[Optional[LLMResponse], Optional[str], Optional[str]]:
        """Call OpenRouter API."""
        
        # Base configuration
        base_url = self.settings.openrouter_base_url.rstrip("/")
        api_key = self.settings.openrouter_api_key
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/prsbot",
            "X-Title": "PRSBOT News Monitor"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты анализируешь новости. Отвечай ТОЛЬКО валидным JSON."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 1000
        }
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                
                # Stats tracking
                tokens_in = 0
                tokens_out = 0
                cost = 0.0
                
                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    
                    # Cost is likely 0 for free models, but let's be safe
                    # Only apply cost if model is NOT in free tier list (future proof)
                    if ":free" not in model:
                        cost = (tokens_in * 1.0 + tokens_out * 3.0) / 1_000_000 # Dummy rates
                    
                    raw_content = data["choices"][0]["message"]["content"].strip()
                    
                    # Track Success
                    await LLMMonitor.track_request(
                        provider="openrouter",
                        model=model,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        cost=cost,
                        latency_ms=latency_ms,
                        http_status=200,
                        context=trace_id
                    )
                    
                    parsed = self._parse_response(raw_content)
                    if not parsed:
                         # JSON Error
                        await LLMMonitor.track_request(
                            provider="openrouter", model=model, 
                            http_status=200, error_type="json_parse_error", latency_ms=latency_ms
                        )
                        return None, raw_content, "LLM_INVALID_JSON"
                        
                    return parsed, raw_content, None
                    
                # HTTP Error
                error_type = "http_error"
                if response.status_code == 429: error_type = "rate_limit"
                if response.status_code == 402: error_type = "payment_required"
                
                await LLMMonitor.track_request(
                    provider="openrouter",
                    model=model,
                    cost=0.0,
                    latency_ms=latency_ms,
                    http_status=response.status_code,
                    error_type=error_type,
                    context=trace_id
                )
                
                if response.status_code == 429: return None, None, "LLM_RATE_LIMIT"
                return None, None, "LLM_API_ERROR"

        except httpx.TimeoutException:
            await LLMMonitor.track_request(
                provider="openrouter", model=model, http_status=408, error_type="timeout", context=trace_id
            )
            return None, None, "LLM_TIMEOUT"
            
        except Exception as e:
            logger.error("llm_exception", error=str(e))
            await LLMMonitor.track_request(
                provider="openrouter", model=model, http_status=500, error_type="exception", context=trace_id
            )
            return None, None, "LLM_ERROR"

    def _build_prompt(self, title: str, text: str, region: Optional[str], source: str) -> str:
        """Build analysis prompt."""
        return f"""Проанализируй новость.
ВХОД:
Заголовок: {title}
Источник: {source}
Регион: {region or 'не определён'}
Текст: {text[:1500]}

ЗАДАЧА:
Определи, является ли это ТЕКУЩЕЙ ТЕХНОГЕННОЙ АВАРИЕЙ в ЖКХ или Промышленности.

ИГНОРИРУЙ (relevance=0):
- Плановые работы, отключения, учения
- ДТП, пожары в жилых домах (бытовые)
- Завершенные события ("авария устранена")
- Криминал, политика, коррупция
- Природные явления (без разрушения инфраструктуры)

ВЫХОД (JSON):
{{
  "event_type": "accident | outage | repair | other",
  "relevance": 0.0-1.0 (0.8+ для серьезных аварий),
  "urgency": 1-5,
  "object": "water | heat | industrial | unknown",
  "why": "Причина решения",
  "action": "call | watch | ignore"
}}"""

    def _parse_response(self, content: str) -> Optional[LLMResponse]:
        """Parse JSON response."""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            content = content.strip()
            data = json.loads(content)
            return LLMResponse.model_validate(data)
        except Exception:
            return None


def should_send_signal(response: LLMResponse, relevance_threshold: float = 0.6, urgency_threshold: int = 3) -> bool:
    """Check thresholds."""
    return (
        response.relevance >= relevance_threshold and
        response.urgency >= urgency_threshold and
        response.action in ("call", "watch")
    )
