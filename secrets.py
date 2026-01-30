# ==============================================================================
# SECRETS & CONFIGURATION
# ==============================================================================
# Читает переменные окружения (для Render.com) или использует значения по умолчанию
# ==============================================================================
import os

# --- API Keys (из переменных окружения или по умолчанию) ---
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "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")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8500861592:AAHj3wJBbsu_wJa2NlavcgoAwA-fDrByO6k")

# --- Bot Password ---
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "1")

# --- Timing ---
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
MAX_ARTICLES_PER_CHECK = int(os.getenv("MAX_ARTICLES_PER_CHECK", "50"))

# --- AI Settings ---
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.3"))
PERPLEXITY_MODEL = "llama-3.1-sonar-large-128k-online"
PERPLEXITY_API_BASE = "https://api.perplexity.ai"

# --- Keywords ---
KEYWORDS = [
    "авария", "прорыв", "остановка", "ремонт", "срочный ремонт",
    "износ", "замена оборудования", "водоснабжение", "канализация",
    "котельная", "насос"
]

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "news_monitor.log"

# --- Database ---
DB_PATH = "news_monitor.db"
