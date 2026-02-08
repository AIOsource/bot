"""Pipeline package."""
from normalize import normalize_news_item, prepare_for_llm
from dedup import Deduplicator, compute_simhash
from filter1 import KeywordFilter, FilterResult, DEFAULT_KEYWORDS, DEFAULT_WEIGHTS
from region import detect_region, RegionDetector
from llm import LLMClient, LLMResponse, should_send_signal
from decision import decide, SignalDecision, get_status_from_decision
from signals import format_signal_message, create_signal_from_llm
from freshness import check_freshness, FreshnessResult
from resolved import check_resolved, ResolvedResult
from noise import check_noise, NoiseResult

__all__ = [
    "normalize_news_item", "prepare_for_llm",
    "Deduplicator", "compute_simhash",
    "KeywordFilter", "FilterResult", "DEFAULT_KEYWORDS", "DEFAULT_WEIGHTS",
    "detect_region", "RegionDetector",
    "LLMClient", "LLMResponse", "should_send_signal",
    "decide", "SignalDecision", "get_status_from_decision",
    "format_signal_message", "create_signal_from_llm",
    "check_freshness", "FreshnessResult",
    "check_resolved", "ResolvedResult",
    "check_noise", "NoiseResult",
]

