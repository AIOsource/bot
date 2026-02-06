"""YAML config loader with DB overrides support."""
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass, field


class SourceConfig(BaseModel):
    """Single source configuration."""
    id: str
    type: str = "rss"  # rss, web, google_news_rss
    name: str
    url: Optional[str] = None
    query: Optional[str] = None  # For google_news_rss
    region_hint: Optional[str] = None
    hl: str = "ru"
    gl: str = "RU"
    ceid: str = "RU:ru"


class KeywordsConfig(BaseModel):
    """Keywords configuration."""
    positive: Dict[str, list[str]] = Field(default_factory=dict)
    negative: list[str] = Field(default_factory=list)


class WeightsConfig(BaseModel):
    """Scoring weights."""
    accident: int = 3
    repair: int = 2
    infrastructure: int = 4
    industrial: int = 2
    negative: int = -5


class ThresholdsConfig(BaseModel):
    """Filtering thresholds."""
    filter1_to_llm: int = 4
    llm_relevance: float = 0.6
    llm_urgency: int = 3


class LimitsConfig(BaseModel):
    """System limits."""
    max_signals_per_day: int = 5


class DedupConfig(BaseModel):
    """Deduplication settings."""
    simhash_threshold: int = 3
    url_params_to_remove: list[str] = Field(default_factory=lambda: [
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "yclid", "gclid", "fbclid", "ref", "from", "source", "rss", "tg"
    ])


class HttpConfig(BaseModel):
    """HTTP client settings."""
    timeout: int = 15
    retries: int = 3


class ScheduleConfig(BaseModel):
    """Scheduler settings."""
    check_interval_minutes: int = 30


class FreshnessConfig(BaseModel):
    """Freshness filter settings."""
    max_age_days: int = 21
    allow_missing_published_at: bool = True
    fallback_to_collected_at: bool = True


class ResolvedFilterConfig(BaseModel):
    """Resolved (already fixed) filter settings."""
    enabled: bool = True
    hard_resolved_phrases: list[str] = Field(default_factory=list)
    soft_resolved_words: list[str] = Field(default_factory=list)
    allow_if_still_ongoing_words: list[str] = Field(default_factory=list)
    mode: str = "block_resolved"


class NoiseFilterConfig(BaseModel):
    """Noise (death/crime) filter settings."""
    enabled: bool = True
    hard_negative_topics: list[str] = Field(default_factory=list)
    бытовое_шум: list[str] = Field(default_factory=list, alias="бытовое_шум")
    exception_infra_phrases: list[str] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True


class Filter1GateConfig(BaseModel):
    """Filter1 combo gate settings."""
    require_combo_to_llm: bool = True
    event_categories_required: list[str] = Field(default_factory=lambda: ["accident", "repair"])
    object_categories_required: list[str] = Field(default_factory=lambda: ["infrastructure", "industrial"])


class LLMThrottleConfig(BaseModel):
    """LLM throttling settings."""
    max_requests_per_cycle: int = 30
    max_requests_per_minute: int = 30
    concurrency: int = 1
    backoff_on_429_seconds: list[int] = Field(default_factory=lambda: [2, 5, 10, 20, 40])
    max_consecutive_429: int = 3


class UIMessagesConfig(BaseModel):
    """UI message templates."""
    welcome_new: str = "Привет. Подписка включена."
    welcome_existing: str = "Подписка уже активна."
    admin_suffix: str = "\n\nВы администратор."
    stop: str = "Подписка отключена."
    status: str = "Статус: подписка активна"
    help: str = "Команды: /status /stop /privacy"
    privacy: str = "Используются только открытые источники."


class UIConfig(BaseModel):
    """UI settings."""
    messages: UIMessagesConfig = Field(default_factory=UIMessagesConfig)


class AppConfig(BaseModel):
    """Complete application configuration."""
    sources: list[SourceConfig] = Field(default_factory=list)
    keywords: KeywordsConfig = Field(default_factory=KeywordsConfig)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    # New quality filters
    freshness: FreshnessConfig = Field(default_factory=FreshnessConfig)
    resolved_filter: ResolvedFilterConfig = Field(default_factory=ResolvedFilterConfig)
    noise_filter: NoiseFilterConfig = Field(default_factory=NoiseFilterConfig)
    filter1_gate: Filter1GateConfig = Field(default_factory=Filter1GateConfig)
    llm_throttle: LLMThrottleConfig = Field(default_factory=LLMThrottleConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


class ConfigLoader:
    """Load configuration from YAML with DB overrides."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / "config" / "config.yaml"
        self._config: Optional[AppConfig] = None
        self._overrides: Dict[str, Any] = {}
    
    def load(self) -> AppConfig:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            # Return default config if file doesn't exist
            self._config = AppConfig()
            return self._config
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        # Parse sources
        sources = []
        for src in data.get("sources", []):
            sources.append(SourceConfig(**src))
        data["sources"] = sources
        
        self._config = AppConfig(**data)
        self._apply_overrides()
        return self._config
    
    def set_overrides(self, overrides: Dict[str, Any]) -> None:
        """Set DB overrides to apply on top of YAML config."""
        self._overrides = overrides
        if self._config:
            self._apply_overrides()
    
    def _apply_overrides(self) -> None:
        """Apply DB overrides to current config."""
        if not self._config or not self._overrides:
            return
        
        for key, value in self._overrides.items():
            self._set_nested(key, value)
    
    def _set_nested(self, key: str, value: Any) -> None:
        """Set a nested config value using dot notation."""
        parts = key.split(".")
        obj = self._config
        
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return
        
        final_key = parts[-1]
        if hasattr(obj, final_key):
            # Convert value to appropriate type
            current = getattr(obj, final_key)
            if isinstance(current, int):
                value = int(value)
            elif isinstance(current, float):
                value = float(value)
            elif isinstance(current, bool):
                value = str(value).lower() in ("true", "1", "yes")
            setattr(obj, final_key, value)
    
    def reload(self) -> AppConfig:
        """Reload configuration from file."""
        return self.load()
    
    @property
    def config(self) -> AppConfig:
        """Get current config, loading if necessary."""
        if self._config is None:
            self.load()
        return self._config


# Global config loader instance
_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get global config loader instance."""
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
    return _loader


def get_config() -> AppConfig:
    """Get current application config."""
    return get_config_loader().config
