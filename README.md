# PRSBOT - Russian Infrastructure News Monitor

Telegram bot for monitoring infrastructure incidents (ЖКХ/industrial) in Russia.

## Features

- **Multi-source collection**: RSS feeds, Google News, web scraping from 30+ sources
- **Two-level deduplication**: URL normalization + simhash text similarity
- **Two-stage filtering**: Keyword scoring (Filter 1) + LLM classification (Filter 2)
- **Smart alerts**: Max 5 signals/day, formatted notifications with relevance/urgency
- **Admin panel**: Stats, config management, source control via Telegram

## Quick Start

```bash
# Clone and install
cd PRSBOT
pip install -e .

# Configure
cp .env.example .env
# Edit .env with your tokens

# Run
python -m prsbot.main
```

## Configuration

### Environment Variables (`.env`)

```env
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_chat_id
OPENROUTER_API_KEY=your_api_key
APP_TIMEZONE=Asia/Yekaterinburg
DATABASE_URL=sqlite+aiosqlite:///./data/prsbot.db
LOG_LEVEL=INFO
```

### YAML Config (`config/config.yaml`)

- **sources**: RSS feeds, web scrapers, Google News queries
- **keywords**: Positive/negative keyword lists by category
- **weights**: Scoring weights for each category
- **thresholds**: Filter1 pass score, LLM relevance/urgency thresholds
- **limits**: Max signals per day

## Bot Commands

### User Commands
- `/start` - Subscribe to alerts
- `/stop` - Unsubscribe
- `/help` - Show help
- `/status` - Your subscription status

### Admin Commands
- `/admin` - Admin panel
- `/stats` - Daily/weekly statistics
- `/config_show` - Current config
- `/config_set <key> <value>` - Update config
- `/sources_list` - List sources
- `/broadcast <text>` - Send message to all

## Architecture

```
prsbot/
├── settings.py          # Environment config
├── config_loader.py     # YAML config + DB overrides
├── logging_setup.py     # Structured JSON logging
├── main.py              # Entry point with scheduler
├── db/                  # SQLAlchemy models & repos
├── sources/             # RSS & web fetchers
├── pipeline/            # Processing stages
│   ├── normalize.py     # Text normalization
│   ├── dedup.py         # Simhash deduplication
│   ├── filter1.py       # Keyword scoring
│   ├── region.py        # Region detection
│   ├── llm.py           # OpenRouter client
│   ├── decision.py      # Signal decision
│   └── signals.py       # Message formatting
├── bot/                 # Telegram handlers
└── reports/             # Weekly reports
```

## Pipeline Flow

```
Sources → Fetch → Normalize → Dedup → Filter1 → LLM → Decision → Signal → Broadcast
                    ↓           ↓         ↓        ↓       ↓          ↓
                  DB:raw    Skip dup  score<4   relevance  limit   Telegram
                                      → filter  <0.6 or   check   subscribers
                                                urgency<3
```

## Testing

```bash
pytest tests/ -v
```

## License

Private/Internal use only.
