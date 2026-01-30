# Руководство по установке и настройке

## Структура проекта

```
BOT/
├── main.py          # Главный файл запуска
├── config.py        # Конфигурация и RSS источники
├── telegram_bot.py  # Telegram бот
├── ai_filter.py     # AI фильтрация через Perplexity
├── news_collector.py # Сбор новостей из RSS
├── database.py      # Работа с SQLite
├── models.py        # Модели данных
├── utils.py         # Утилиты
├── requirements.txt # Зависимости Python
├── .env             # Переменные окружения (создать)
└── .env.example     # Пример переменных
```

## Переменные окружения (.env)

Создайте файл `.env` в корне проекта:

```env
# ОБЯЗАТЕЛЬНЫЕ
PERPLEXITY_API_KEY=pplx-xxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-xxx

# ОПЦИОНАЛЬНЫЕ
CHECK_INTERVAL_MINUTES=30
MAX_ARTICLES_PER_CHECK=50
RELEVANCE_THRESHOLD=0.6
KEYWORDS=авария,прорыв,остановка,ремонт,насос
LOG_LEVEL=INFO
```

### Где получить ключи:

1. **PERPLEXITY_API_KEY**: https://www.perplexity.ai/settings/api
2. **TELEGRAM_BOT_TOKEN**: создать бота через @BotFather в Telegram

---

## Установка

### Windows (PowerShell)

```powershell
# Перейти в папку проекта
cd C:\путь\к\BOT

# Создать виртуальное окружение
python -m venv venv

# Активировать venv
.\venv\Scripts\Activate.ps1

# Установить зависимости
pip install -r requirements.txt

# Запуск
python main.py
```

### Linux / macOS (Bash)

```bash
# Перейти в папку проекта
cd /путь/к/BOT

# Создать виртуальное окружение
python3 -m venv venv

# Активировать venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Запуск
python main.py
```

---

## Использование Telegram бота

1. Найдите бота по имени в Telegram
2. Отправьте команду `/start`
3. Введите пароль: `1` (по умолчанию)
4. Используйте меню для управления

### Команды бота:

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/check` | Ручное сканирование |
| `/stats` | Статистика системы |
| `/settings` | Настройки |
| `/help` | Справка |

---

## Изменение пароля

В файле `telegram_bot.py` найдите строку:

```python
BOT_PASSWORD = "1"
```

Замените `"1"` на ваш пароль.

---

## Настройка порога релевантности

В файле `.env`:

```env
RELEVANCE_THRESHOLD=0.6
```

- `0.3` — низкий порог, больше событий
- `0.6` — средний порог (рекомендуется)
- `0.9` — высокий порог, только критичные

---

## Логи

Логи записываются в файл `news_monitor.log`

---

## Автор

@SalutByBase
