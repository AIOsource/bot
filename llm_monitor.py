"""LLM usage monitoring and statistics (v1.7.0)."""
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from db_pkg import get_session, LLMUsageRepository, ConfigRepository
from models import LLMUsage

class BudgetExceededError(Exception):
    """Raised when daily budget is exceeded."""
    pass

class CircuitBreaker:
    """Circuit breaker for LLM providers."""
    
    _errors: list[datetime] = []
    _window_minutes: int = 5
    _threshold: int = 5  # errors in window
    _is_open: bool = False
    _last_error_at: Optional[datetime] = None
    _cooldown_minutes: int = 10
    
    @classmethod
    def record_error(cls):
        """Record an error occurrence."""
        now = datetime.utcnow()
        cls._last_error_at = now
        cls._errors.append(now)
        cls._cleanup()
        
        if len(cls._errors) >= cls._threshold:
            cls._is_open = True
            
    @classmethod
    def record_success(cls):
        """Record success, potentially closing circuit."""
        if cls._is_open:
            # If we are here, it means a request succeeded (maybe probe)
            # Close circuit
            cls._is_open = False
            cls._errors = []
            
    @classmethod
    def is_open(cls) -> bool:
        """Check if circuit is open (broken)."""
        if not cls._is_open:
            return False
            
        # Check cooldown
        if cls._last_error_at:
            elapsed = datetime.utcnow() - cls._last_error_at
            if elapsed > timedelta(minutes=cls._cooldown_minutes):
                # Cooldown passed, allow probe
                return False
                
        return True
        
    @classmethod
    def _cleanup(cls):
        """Remove old errors from window."""
        cutoff = datetime.utcnow() - timedelta(minutes=cls._window_minutes)
        cls._errors = [t for t in cls._errors if t > cutoff]


class LLMMonitor:
    """Monitor for LLM usage and guardrails."""
    
    @staticmethod
    async def check_budget() -> None:
        """Check if daily budget is exceeded.
        
        Raises:
            BudgetExceededError: If limit reached.
        """
        # Load config
        from config_loader import get_config
        config = get_config()
        
        # Default target $0.00 for free models
        limit = 0.00 
        
        # Check if overrides exist
        # We can implement specific config key later, for now we assume $0.00 target
        # unless strictly configured otherwise.
        # Ideally we'd read `llm.budget_limit` from config.
        # For this requirement: "Target: $0.00"
        
        async with get_session() as session:
            spent = await LLMUsageRepository.get_daily_cost(session)
            
        # Allow tiny margin for FP math
        if spent > limit + 0.001:
            raise BudgetExceededError(f"Daily budget limit exceeded: ${spent:.4f} > ${limit}")

    @staticmethod
    async def track_request(
        provider: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
        latency_ms: int = 0,
        http_status: int = 200,
        error_type: Optional[str] = None,
        context: str = None
    ):
        """Track granular request stats."""
        
        # Update Circuit Breaker
        if http_status != 200 or error_type:
            CircuitBreaker.record_error()
        else:
            CircuitBreaker.record_success()
            
        # DB Log
        stats = {
            "provider": provider,
            "model": model,
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "total_cost": cost,
            "latency_ms": latency_ms,
            "http_status": http_status,
            "error_type": error_type,
            "context": context,
            "timestamp": datetime.utcnow()
        }
        
        async with get_session() as session:
            await LLMUsageRepository.track(session, stats)
            await session.commit()
            
    @staticmethod
    async def get_daily_usage() -> tuple[float, int]:
        """Get today's cost and tokens."""
        async with get_session() as session:
            cost = await LLMUsageRepository.get_daily_cost(session)
            # We could also get tokens if needed, but cost is primary
            return cost, 0 # tokens placeholder

async def init_monitor_db():
    """Initialize monitor tables."""
    from db_pkg import get_db_engine, Base
    db = get_db_engine()
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
