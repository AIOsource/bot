"""OpenRouter LLM client for news classification.

# Adapted from other/3/core/llm.py - LLMClient class
"""
import json
from typing import Optional, Literal
import httpx
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from logging_setup import get_logger
from settings import Settings

logger = get_logger("pipeline.llm")


class LLMResponse(BaseModel):
    """Strict output schema for LLM classification."""
    event_type: Literal["accident", "outage", "repair", "other"]
    relevance: float = Field(ge=0.0, le=1.0)
    urgency: int = Field(ge=1, le=5)
    object: Literal["water", "heat", "industrial", "unknown"]
    why: str
    action: Literal["call", "watch", "ignore"]


# Russian translations for event types
EVENT_TYPE_RU = {
    "accident": "авария",
    "outage": "остановка",
    "repair": "ремонт",
    "other": "другое"
}

OBJECT_TYPE_RU = {
    "water": "ЖКХ (водоснабжение)",
    "heat": "ЖКХ (теплоснабжение)",
    "industrial": "промышленность",
    "unknown": "не определено"
}


class OpenRouterClient:
    """Async client for OpenRouter LLM API with throttling."""
    
    def __init__(self, settings: Settings):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url.rstrip("/")
        
        # Throttle state
        self.requests_this_cycle = 0
        self.consecutive_429 = 0
        self.disabled_for_cycle = False
        self.last_error_code: Optional[str] = None
        
        # Config (can be overridden)
        self.max_requests_per_cycle = 30
        self.max_consecutive_429 = 3
        self.backoff_seconds = [2, 5, 10, 20, 40]
    
    def reset_cycle(self):
        """Reset throttle state for new cycle."""
        self.requests_this_cycle = 0
        self.consecutive_429 = 0
        self.disabled_for_cycle = False
        self.last_error_code = None
    
    def is_available(self) -> tuple[bool, Optional[str]]:
        """Check if LLM is available for requests.
        
        Returns:
            (available, reason_if_not)
        """
        if self.disabled_for_cycle:
            return False, self.last_error_code or "LLM_DISABLED"
        if self.requests_this_cycle >= self.max_requests_per_cycle:
            return False, "LLM_CYCLE_LIMIT"
        if self.consecutive_429 >= self.max_consecutive_429:
            return False, "LLM_RATE_LIMIT_EXCEEDED"
        return True, None
    
    async def analyze(
        self,
        title: str,
        text: str,
        region: Optional[str] = None,
        source: str = "",
        trace_id: str = ""
    ) -> tuple[Optional[LLMResponse], Optional[str], Optional[str]]:
        """
        Analyze news article for relevance.
        
        Args:
            title: Article title
            text: Article text (pre-truncated to ~10 sentences)
            region: Detected region
            source: Source name
            trace_id: Trace ID for logging
        
        Returns:
            (LLMResponse or None, raw_response_str or None, error_code or None)
        """
        prompt = self._build_prompt(title, text, region, source)
        
        # First attempt
        response, raw, error_code = await self._call_api(prompt, trace_id)
        if response:
            return response, raw, None
        
        # Don't retry on rate/billing limits
        if error_code in ("LLM_RATE_LIMIT", "LLM_BILLING_LIMIT", "LLM_CYCLE_LIMIT", "LLM_RATE_LIMIT_EXCEEDED"):
            return None, raw, error_code
        
        # Retry with explicit JSON instruction for parse errors
        if error_code == "LLM_INVALID_JSON":
            logger.info("llm_retry", trace_id=trace_id, reason="invalid_json")
            retry_prompt = f"{prompt}\n\nВерни строго JSON без какого-либо обрамления или текста вокруг."
            return await self._call_api(retry_prompt, trace_id)
        
        return None, raw, error_code
    
    def _build_prompt(
        self,
        title: str,
        text: str,
        region: Optional[str],
        source: str
    ) -> str:
        """Build analysis prompt with strict JSON-only instruction."""
        return f"""Проанализируй новость и определи её релевантность для мониторинга ЖКХ/промышленности.

ВХОДНЫЕ ДАННЫЕ:
Заголовок: {title}
Источник: {source}
Регион: {region or 'не определён'}
Текст: {text[:1200]}

КРИТИЧНО ИГНОРИРУЙ (relevance<=0.2, urgency<=2, action="ignore"):
- Событие УЖЕ ЗАВЕРШЕНО/УСТРАНЕНО (авария устранена, работы завершены, подача воды восстановлена)
- Смерть/гибель человека (если НЕ техногенная авария на инфраструктуре)
- Криминал, суд, арест, расследование
- Бытовые конфликты, квартирные вопросы
- Наличие слова "водоканал/насос" НЕ означает релевантность, если новость НЕ про аварию/отключение/ремонт

ТАКЖЕ ИГНОРИРУЙ (relevance=0):
- ДТП и автомобильные аварии
- Ремонт дорог и мостов
- Учения и тренировки
- Закупки, тендеры, финансы
- Метафоры ("политическая авария")

ВЫСОКАЯ РЕЛЕВАНТНОСТЬ (relevance>=0.7, urgency>=3):
- Прорывы труб водоснабжения/отопления (ТЕКУЩИЕ, не устранённые)
- Аварии на насосных станциях (КНС, ВНС)
- Остановки котельных
- Аварии на очистных сооружениях
- Серьёзные промышленные аварии

ОТВЕТЬ ТОЛЬКО ВАЛИДНЫМ JSON БЕЗ КАКОГО-ЛИБО ТЕКСТА ВОКРУГ:
{{
  "event_type": "accident | outage | repair | other",
  "relevance": 0.0-1.0,
  "urgency": 1-5,
  "object": "water | heat | industrial | unknown",
  "why": "Краткое объяснение (1 предложение)",
  "action": "call | watch | ignore"
}}"""
    
    async def _call_api(self, prompt: str, trace_id: str = "") -> tuple[Optional[LLMResponse], Optional[str], Optional[str]]:
        """Make API call to OpenRouter with throttling.
        
        Returns:
            (parsed_response, raw_content, error_code)
        """
        import asyncio
        import random
        
        raw_content = None
        
        # Check availability
        available, reason = self.is_available()
        if not available:
            logger.info("llm_skipped", trace_id=trace_id, reason=reason)
            return None, None, reason
        
        self.requests_this_cycle += 1
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/prsbot",
                        "X-Title": "PRSBOT News Monitor"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Ты анализируешь новости. Отвечай ТОЛЬКО валидным JSON. Никакого markdown, текста, комментариев. Только JSON."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 500
                    }
                )
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    self.consecutive_429 += 1
                    
                    # Get backoff time
                    backoff_idx = min(self.consecutive_429 - 1, len(self.backoff_seconds) - 1)
                    backoff = self.backoff_seconds[backoff_idx]
                    jitter = random.uniform(0.5, 1.5)
                    wait_time = backoff * jitter
                    
                    logger.warning(
                        "llm_rate_limited",
                        trace_id=trace_id,
                        status_code=429,
                        consecutive_429=self.consecutive_429,
                        backoff_seconds=round(wait_time, 1)
                    )
                    
                    # Short-circuit if too many 429s
                    if self.consecutive_429 >= self.max_consecutive_429:
                        self.last_error_code = "LLM_RATE_LIMIT_EXCEEDED"
                        return None, None, "LLM_RATE_LIMIT"
                    
                    # Wait and signal rate limit
                    await asyncio.sleep(wait_time)
                    return None, None, "LLM_RATE_LIMIT"
                
                # Handle billing limit (402)
                if response.status_code == 402:
                    self.disabled_for_cycle = True
                    self.last_error_code = "LLM_BILLING_LIMIT"
                    logger.error(
                        "llm_billing_limit",
                        trace_id=trace_id,
                        body=response.text[:200]
                    )
                    return None, None, "LLM_BILLING_LIMIT"
                
                # Handle other errors
                if response.status_code != 200:
                    logger.error(
                        "llm_api_error",
                        trace_id=trace_id,
                        status_code=response.status_code,
                        body=response.text[:200]
                    )
                    return None, None, "LLM_API_ERROR"
                
                # Success - reset consecutive 429 counter
                self.consecutive_429 = 0
                
                data = response.json()
                raw_content = data["choices"][0]["message"]["content"].strip()
                
                parsed = self._parse_response(raw_content)
                if parsed is None:
                    return None, raw_content, "LLM_INVALID_JSON"
                
                return parsed, raw_content, None
                
        except httpx.TimeoutException:
            logger.error("llm_timeout", trace_id=trace_id)
            return None, raw_content, "LLM_TIMEOUT"
        except Exception as e:
            logger.error("llm_error", trace_id=trace_id, error=str(e))
            return None, raw_content, "LLM_ERROR"
    
    def _parse_response(self, content: str) -> Optional[LLMResponse]:
        """Parse and validate LLM response."""
        try:
            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            content = content.strip()
            
            # Parse JSON
            data = json.loads(content)
            
            # Validate with pydantic
            return LLMResponse.model_validate(data)
            
        except json.JSONDecodeError as e:
            logger.warning("llm_json_error", error=str(e), content=content[:100])
            return None
        except ValidationError as e:
            logger.warning("llm_validation_error", error=str(e))
            return None


def should_send_signal(response: LLMResponse, relevance_threshold: float = 0.6, urgency_threshold: int = 3) -> bool:
    """
    Determine if LLM response warrants a signal.
    
    Rule: relevance >= 0.6 AND urgency >= 3
    """
    return (
        response.relevance >= relevance_threshold and
        response.urgency >= urgency_threshold and
        response.action in ("call", "watch")
    )
