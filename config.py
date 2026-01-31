from typing import List
import secrets as cfg


class Config:
    # --- API Configuration ---
    PERPLEXITY_API_KEY: str = cfg.PERPLEXITY_API_KEY
    PERPLEXITY_API_BASE: str = cfg.PERPLEXITY_API_BASE
    PERPLEXITY_MODEL: str = cfg.PERPLEXITY_MODEL
    TELEGRAM_BOT_TOKEN: str = cfg.TELEGRAM_BOT_TOKEN
    BOT_PASSWORD: str = cfg.BOT_PASSWORD
    
    # --- Timing ---
    CHECK_INTERVAL_MINUTES: int = cfg.CHECK_INTERVAL_MINUTES
    MAX_ARTICLES_PER_CHECK: int = cfg.MAX_ARTICLES_PER_CHECK
    
    # --- AI Settings ---
    RELEVANCE_THRESHOLD: float = cfg.RELEVANCE_THRESHOLD
    KEYWORDS: List[str] = cfg.KEYWORDS
    
    # --- Logging & DB ---
    LOG_LEVEL: str = cfg.LOG_LEVEL
    LOG_FILE: str = cfg.LOG_FILE
    DB_PATH: str = cfg.DB_PATH

    # --- Stage 2 Filtering Rules ---
    # Positive Keywords (Global) - presence increases score
    KEYWORDS_POSITIVE: List[str] = [
        "авария", "прорыв", "утечка", "порыв", "остановка", "вышел из строя", "чп",
        "ремонт", "срочный ремонт", "капремонт", "замена", "реконструкция", "модернизация",
        "водоканал", "насосная станция", "кнс", "котельная", "теплосети", "очистные сооружения",
        "цех", "агрегат", "производство", "простой", "технологический сбой"
    ]
    
    # Negative Keywords (Global) - presence decreases score or blocks
    KEYWORDS_NEGATIVE: List[str] = [
        "дтп", "авария автомобиля", "ремонт дороги", "ремонт моста",
        "учения", "тренировка", "условная авария",
        "бытовой ремонт", "квартира", "подъезд"
    ]
    
    # Scoring Weights
    SCORE_WEIGHTS: dict = {
        "accident": 3,   # авария/остановка
        "repair": 2,     # ремонт/замена
        "infra": 4,      # объект инфраструктуры
        "industry": 2,   # пром объект
        "negative": -5   # стоп-слова
    }
    
    # Thresholds
    KEYWORD_SCORE_THRESHOLD: int = 4  # Minimum score to send to LLM
    LLM_RELEVANCE_THRESHOLD: float = 0.6
    LLM_URGENCY_THRESHOLD: int = 3
    
    LLM_URGENCY_THRESHOLD: int = 3
    
    @property
    def RSS_SOURCES(self) -> List[dict]:
        import json
        import os
        try:
            if os.path.exists('sources.json'):
                with open('sources.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading sources.json: {e}")
            
        return [
            {"name": "Google", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "test"},
            {"name": "Яндекс ЖКХ", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "aggregator"},
            {"name": "Яндекс Происшествия", "url": "https://news.yandex.ru/incident.rss", "category": "aggregator"},
            {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml", "category": "federal"},
            {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml", "category": "federal"},
            {"name": "МЧС России", "url": "http://www.mchs.gov.ru/news/rss/", "category": "emergency"},
        ]
        
    def get_sources(self):
        # Helper since we changed RSS_SOURCES to property we need to instantiate or handle 
        # But wait, config is a class used as config.RSS_SOURCES usually.
        # If I change it to property on class, I need instance.
        # The code uses `config.RSS_SOURCES` where `config` is an INSTANCE in `config.py`.
        # Let's check `config.py` end of file.
        return self.RSS_SOURCES
    WEB_SOURCES: List[dict] = [
        {"name": "Закупки.gov.ru", "url": "https://zakupki.gov.ru/epz/main/public/home.html", "category": "procurement", "type": "web_scraping"},
        {"name": "TenderGuru", "url": "https://www.tenderguru.ru", "category": "procurement", "type": "api"},
        {"name": "РосТендер", "url": "https://rostender.info", "category": "procurement", "type": "web_scraping"},
        {"name": "Ros-Tender.ru", "url": "https://ros-tender.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "Сбербанк-АСТ", "url": "https://www.sberbank-ast.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "РТС-Тендер", "url": "https://www.rts-tender.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "Росэлторг", "url": "https://www.roseltorg.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "ЭТП ЕТС", "url": "https://etp-ets.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "ТЭК-Торг", "url": "https://tek-torg.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "B2B-Center", "url": "https://b2b-center.ru", "category": "procurement", "type": "web_scraping"},
        {"name": "Росстат", "url": "https://rosstat.gov.ru", "category": "statistics", "type": "web_scraping"},
        {"name": "TrueStats", "url": "https://truestats.ru", "category": "statistics", "type": "web_scraping"},
        {"name": "StatBase", "url": "https://statbase.ru", "category": "statistics", "type": "web_scraping"},
        {"name": "ClearSpending", "url": "https://clearspending.ru", "category": "procurement_analytics", "type": "web_scraping"},
    ]
    
    @classmethod
    def validate(cls) -> bool:
        if not cls.PERPLEXITY_API_KEY:
            raise ValueError("PERPLEXITY_API_KEY is required")
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        return True


config = Config()
