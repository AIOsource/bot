"""Signal decision logic and formatting."""
from typing import Optional
from dataclasses import dataclass

from llm import LLMResponse
from logging_setup import get_logger

logger = get_logger("pipeline.decision")


@dataclass
class SignalDecision:
    """Decision about whether to send a signal."""
    should_send: bool
    reason: str
    suppressed: bool = False  # True if suppressed by limit


def decide(
    llm_response: Optional[LLMResponse],
    filter1_score: int,
    filter1_passed: bool,
    signals_today: int,
    max_signals_per_day: int = 5,
    relevance_threshold: float = 0.6,
    urgency_threshold: int = 3
) -> SignalDecision:
    """
    Make final decision on whether to send signal.
    
    Args:
        llm_response: LLM classification result (or None if failed)
        filter1_score: Score from keyword filter
        filter1_passed: Whether filter1 passed
        signals_today: Number of signals already sent today
        max_signals_per_day: Daily limit
        relevance_threshold: Min relevance from LLM
        urgency_threshold: Min urgency from LLM
    
    Returns:
        SignalDecision with reasoning
    """
    # Check filter1 first
    if not filter1_passed:
        return SignalDecision(
            should_send=False,
            reason=f"filter1_rejected (score={filter1_score})"
        )
    
    # Check LLM response
    if llm_response is None:
        return SignalDecision(
            should_send=False,
            reason="llm_failed"
        )
    
    # Check LLM criteria
    if llm_response.relevance < relevance_threshold:
        return SignalDecision(
            should_send=False,
            reason=f"low_relevance ({llm_response.relevance:.2f} < {relevance_threshold})"
        )
    
    if llm_response.urgency < urgency_threshold:
        return SignalDecision(
            should_send=False,
            reason=f"low_urgency ({llm_response.urgency} < {urgency_threshold})"
        )
    
    if llm_response.action == "ignore":
        return SignalDecision(
            should_send=False,
            reason="llm_action_ignore"
        )
    
    # Check daily limit
    if signals_today >= max_signals_per_day:
        return SignalDecision(
            should_send=False,
            reason=f"daily_limit_reached ({signals_today}/{max_signals_per_day})",
            suppressed=True
        )
    
    # All checks passed
    return SignalDecision(
        should_send=True,
        reason=f"approved (relevance={llm_response.relevance:.2f}, urgency={llm_response.urgency})"
    )


def get_status_from_decision(decision: SignalDecision, llm_failed: bool = False) -> str:
    """
    Get news status based on decision.
    
    Returns one of: sent, filtered, llm_failed, suppressed_limit
    """
    if llm_failed:
        return "llm_failed"
    
    if decision.should_send:
        return "sent"
    
    if decision.suppressed:
        return "suppressed_limit"
    
    return "filtered"
