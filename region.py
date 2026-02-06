"""Region detection from text and source."""
import json
from pathlib import Path
from typing import Optional, Dict
import re

from logging_setup import get_logger

logger = get_logger("pipeline.region")


class RegionDetector:
    """Detect region from source or text content."""
    
    def __init__(self, city_to_region_path: Path = None):
        self.city_to_region: Dict[str, str] = {}
        
        # Common region patterns (cities -> regions)
        self._default_mappings = {
            # Major cities
            "москва": "Москва",
            "санкт-петербург": "Санкт-Петербург",
            "петербург": "Санкт-Петербург",
            "спб": "Санкт-Петербург",
            "екатеринбург": "Свердловская область",
            "новосибирск": "Новосибирская область",
            "казань": "Республика Татарстан",
            "нижний новгород": "Нижегородская область",
            "челябинск": "Челябинская область",
            "самара": "Самарская область",
            "уфа": "Республика Башкортостан",
            "ростов-на-дону": "Ростовская область",
            "ростов": "Ростовская область",
            "краснодар": "Краснодарский край",
            "воронеж": "Воронежская область",
            "пермь": "Пермский край",
            "красноярск": "Красноярский край",
            "волгоград": "Волгоградская область",
            "омск": "Омская область",
            "тюмень": "Тюменская область",
            "владивосток": "Приморский край",
            "хабаровск": "Хабаровский край",
            "ярославль": "Ярославская область",
            "архангельск": "Архангельская область",
            "сахалин": "Сахалинская область",
            # Regional identifiers
            "свердловская область": "Свердловская область",
            "ленобласть": "Ленинградская область",
            "ленинградская область": "Ленинградская область",
            "московская область": "Московская область",
            "подмосковье": "Московская область",
        }
        
        # Load custom mappings if provided
        if city_to_region_path and city_to_region_path.exists():
            self._load_mappings(city_to_region_path)
    
    def _load_mappings(self, path: Path) -> None:
        """Load city to region mappings from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Lowercase keys for matching
                self.city_to_region = {
                    k.lower(): v for k, v in data.items()
                }
        except Exception as e:
            logger.warning("load_city_mappings_error", error=str(e))
    
    def detect(
        self,
        text: str,
        title: str = "",
        source_region_hint: Optional[str] = None
    ) -> Optional[str]:
        """
        Detect region from article.
        
        Priority:
        1. Source region hint (if defined)
        2. Explicit region in title
        3. City/region mentions in text
        
        Args:
            text: Article text
            title: Article title
            source_region_hint: Region from source config
        
        Returns:
            Detected region or None
        """
        # 1. Use source hint if available
        if source_region_hint:
            return source_region_hint
        
        combined = f"{title} {text}".lower()
        
        # 2. Check title first for region mentions
        title_lower = title.lower()
        for city, region in self._default_mappings.items():
            if city in title_lower:
                return region
        
        # 3. Check loaded mappings
        for city, region in self.city_to_region.items():
            if city in combined:
                return region
        
        # 4. Check default mappings in text
        for city, region in self._default_mappings.items():
            if city in combined:
                return region
        
        # 5. Try to find "область|край|республика" patterns
        region_pattern = r"([А-Яа-яё]+(?:ая|ий|ый)?)\s+(область|край|республика)"
        matches = re.findall(region_pattern, combined, re.IGNORECASE)
        if matches:
            name, type_ = matches[0]
            return f"{name.capitalize()} {type_.lower()}"
        
        return None


# Global instance with default mappings
_detector: Optional[RegionDetector] = None


def get_region_detector(city_to_region_path: Path = None) -> RegionDetector:
    """Get or create region detector."""
    global _detector
    if _detector is None:
        _detector = RegionDetector(city_to_region_path)
    return _detector


def detect_region(
    text: str,
    title: str = "",
    source_region_hint: Optional[str] = None
) -> Optional[str]:
    """Convenience function to detect region."""
    detector = get_region_detector()
    return detector.detect(text, title, source_region_hint)
