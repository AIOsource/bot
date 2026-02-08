"""Weighted keyword scoring filter (Level 1).

# Adapted from other/3/core/filters.py - FilterV1 class
"""
from typing import Tuple, List, Dict
from dataclasses import dataclass

from config_loader import KeywordsConfig, WeightsConfig
from logging_setup import get_logger

logger = get_logger("pipeline.filter1")


@dataclass
class FilterResult:
    """Result of filter1 scoring."""
    score: int
    positive_matches: List[str]
    negative_matches: List[str]
    passed: bool
    categories_matched: List[str]


class KeywordFilter:
    """Weighted keyword scoring filter."""
    
    def __init__(
        self,
        keywords: KeywordsConfig,
        weights: WeightsConfig,
        threshold: int = 4
    ):
        self.keywords = keywords
        self.weights = weights
        self.threshold = threshold
    
    def score(self, text: str) -> FilterResult:
        """
        Calculate weighted score for text.
        
        Args:
            text: Combined title + text to analyze
        
        Returns:
            FilterResult with score and match details
        """
        if not text:
            return FilterResult(
                score=0,
                positive_matches=[],
                negative_matches=[],
                passed=False,
                categories_matched=[]
            )
        
        text_lower = text.lower()
        score = 0
        positive_matches = []
        negative_matches = []
        categories_matched = []
        
        # Check negative keywords first (high priority discard)
        for keyword in self.keywords.negative:
            kw_lower = keyword.lower()
            if kw_lower in text_lower:
                score += self.weights.negative  # Usually negative value
                negative_matches.append(keyword)
        
        # Check positive keywords by category
        for category, keywords in self.keywords.positive.items():
            weight = getattr(self.weights, category, 0)
            category_matched = False
            
            for keyword in keywords:
                kw_lower = keyword.lower()
                if kw_lower in text_lower:
                    if not category_matched:
                        # Count each category only once for scoring
                        score += weight
                        category_matched = True
                        categories_matched.append(category)
                    positive_matches.append(keyword)
        
        passed = score >= self.threshold
        
        logger.debug(
            "filter1_scored",
            score=score,
            threshold=self.threshold,
            positive_count=len(positive_matches),
            negative_count=len(negative_matches),
            passed=passed
        )
        
        return FilterResult(
            score=score,
            positive_matches=positive_matches,
            negative_matches=negative_matches,
            passed=passed,
            categories_matched=categories_matched
        )
    
    def should_send_to_llm(
        self,
        title: str,
        text: str,
        require_combo: bool = False,
        event_categories: List[str] = None,
        object_categories: List[str] = None,
        strong_event_override_enabled: bool = False,
        strong_event_override_phrases: List[str] = None,
        trace_id: str = ""
    ) -> Tuple[bool, FilterResult, str]:
        """
        Determine if article should be sent to LLM.
        
        Args:
            title: Article title
            text: Article text
            require_combo: If True, require both event and object categories
            event_categories: List of event categories (accident, repair)
            object_categories: List of object categories (infrastructure, industrial)
            strong_event_override_enabled: If True, bypass combo if strong phrase found
            strong_event_override_phrases: List of phrases that bypass combo rule
            trace_id: Trace ID for logging
        
        Returns:
            (should_send, filter_result, decision_code)
        """
        combined = f"{title} {text}"
        result = self.score(combined)
        
        # Default decision code
        decision_code = "PASSED" if result.passed else "FILTER1_BELOW_THRESHOLD"
        
        if not result.passed:
            return False, result, decision_code
        
        # Combo rule check
        if require_combo and event_categories and object_categories:
            has_event = any(cat in result.categories_matched for cat in event_categories)
            has_object = any(cat in result.categories_matched for cat in object_categories)
            
            if not (has_event and has_object):
                # Check for strong event override BEFORE failing
                if strong_event_override_enabled and strong_event_override_phrases:
                    combined_lower = combined.lower()
                    for phrase in strong_event_override_phrases:
                        if phrase.lower() in combined_lower:
                            logger.info(
                                "filter1_strong_override",
                                trace_id=trace_id,
                                matched_phrase=phrase,
                                categories_matched=result.categories_matched
                            )
                            decision_code = "STRONG_OVERRIDE"
                            return True, result, decision_code
                
                decision_code = "COMBO_RULE_FAILED"
                logger.info(
                    "combo_rule_failed",
                    trace_id=trace_id,
                    categories_matched=result.categories_matched,
                    has_event=has_event,
                    has_object=has_object
                )
                # Return passed=False with decision code
                return False, FilterResult(
                    score=result.score,
                    positive_matches=result.positive_matches,
                    negative_matches=result.negative_matches,
                    passed=False,
                    categories_matched=result.categories_matched
                ), decision_code
        
        return True, result, decision_code


# Default keywords and weights from specification
DEFAULT_KEYWORDS = KeywordsConfig(
    positive={
        "accident": [
            "авария", "прорыв", "утечка", "порыв", "остановка",
            "вышел из строя", "ЧП", "чрезвычайная ситуация", "аварийный"
        ],
        "repair": [
            "ремонт", "срочный ремонт", "капремонт", "капитальный ремонт",
            "замена", "реконструкция", "модернизация", "восстановление"
        ],
        "infrastructure": [
            "водоканал", "насосная станция", "КНС", "ВНС",
            "котельная", "теплосети", "очистные сооружения",
            "водопровод", "канализация", "теплотрасса"
        ],
        "industrial": [
            "цех", "агрегат", "производство", "простой",
            "технологический сбой", "остановка производства"
        ]
    },
    negative=[
        "ДТП", "дорожно-транспортное происшествие",
        "ремонт дороги", "ремонт моста", "дорожные работы",
        "учения", "тренировка", "условная авария", "плановые учения",
        "квартира", "подъезд", "бытовой", "домашний",
        "автомобиль", "машина столкнулась"
    ]
)

DEFAULT_WEIGHTS = WeightsConfig(
    accident=3,
    repair=2,
    infrastructure=4,
    industrial=2,
    negative=-5
)
