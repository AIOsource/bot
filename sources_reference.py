"""
Extended RSS sources configuration with 30+ sources across Russia.
"""

# Новостные агрегаторы
NEWS_AGGREGATORS = [
    {
        "name": "Яндекс - ЖКХ",
        "url": "https://news.yandex.ru/housing_and_public_utilities.rss",
        "category": "aggregator",
        "priority": "high"
    },
    {
        "name": "Яндекс - Происшествия",
        "url": "https://news.yandex.ru/incident.rss",
        "category": "aggregator",
        "priority": "high"
    },
    {
        "name": "Яндекс - Москва",
        "url": "https://news.yandex.ru/Moscow/index.rss",
        "category": "aggregator_regional",
        "priority": "medium"
    },
]

# МЧС и официальные источники
OFFICIAL_SOURCES = [
    {
        "name": "МЧС России",
        "url": "https://mchs.gov.ru/feed",
        "category": "emergency",
        "priority": "critical"
    },
    {
        "name": "Правительство РФ",
        "url": "http://government.ru/all/rss/",
        "category": "government",
        "priority": "low"
    },
]

# Региональные СМИ - Москва и МО
MOSCOW_SOURCES = [
    {
        "name": "Московский Комсомолец",
        "url": "https://www.mk.ru/rss/index.xml",
        "category": "regional_moscow",
        "priority": "high"
    },
    {
        "name": "Москва 24",
        "url": "https://www.m24.ru/rss.xml",
        "category": "regional_moscow",
        "priority": "high"
    },
]

# Санкт-Петербург
SPB_SOURCES = [
    {
        "name": "Фонтанка",
        "url": "https://www.fontanka.ru/fontanka.rss",
        "category": "regional_spb",
        "priority": "high"
    },
    {
        "name": "Невские Новости",
        "url": "https://nevnov.ru/rss/all.xml",
        "category": "regional_spb",
        "priority": "medium"
    },
    {
        "name": "Деловой Петербург",
        "url": "https://www.dp.ru/RSS",
        "category": "regional_spb",
        "priority": "medium"
    },
]

# Урал (Екатеринбург, Челябинск, Тюмень)
URAL_SOURCES = [
    {
        "name": "Е1.ру (Екатеринбург)",
        "url": "https://www.e1.ru/text/rss.xml",
        "category": "regional_ural",
        "priority": "high"
    },
    {
        "name": "66.ru (Екатеринбург)",
        "url": "https://66.ru/rss/",
        "category": "regional_ural",
        "priority": "medium"
    },
    {
        "name": "URA.news",
        "url": "https://ura.news/feeds/rss",
        "category": "regional_ural",
        "priority": "medium"
    },
    {
        "name": "74.ru (Челябинск)",
        "url": "https://74.ru/text/rss.xml",
        "category": "regional_ural",
        "priority": "medium"
    },
]

# Сибирь (Новосибирск, Омск, Красноярск)
SIBERIA_SOURCES = [
    {
        "name": "НГС.Новости",
        "url": "https://news.ngs.ru/rss/",
        "category": "regional_siberia",
        "priority": "high"
    },
    {
        "name": "Сиб.фм",
        "url": "https://sib.fm/rss",
        "category": "regional_siberia",
        "priority": "medium"
    },
    {
        "name": "НГС54 (Новосибирск)",
        "url": "https://ngs54.ru/text/news/rss.xml",
        "category": "regional_siberia",
        "priority": "medium"
    },
]

# Поволжье (Казань, Самара, Нижний Новгород)
VOLGA_SOURCES = [
    {
        "name": "Бизнес-Онлайн (Казань)",
        "url": "https://www.business-gazeta.ru/rss/",
        "category": "regional_volga",
        "priority": "medium"
    },
    {
        "name": "Казань Онлайн",
        "url": "https://kazanonline.ru/feed/",
        "category": "regional_volga",
        "priority": "high"
    },
    {
        "name": "Самара 24",
        "url": "https://www.samara24.ru/feed/",
        "category": "regional_volga",
        "priority": "medium"
    },
]

# Юг (Краснодар, Ростов, Волгоград)
SOUTH_SOURCES = [
    {
        "name": "КП Краснодар",
        "url": "https://www.kuban.kp.ru/rss/",
        "category": "regional_south",
        "priority": "high"
    },
    {
        "name": "Юга.ру",
        "url": "https://www.yuga.ru/news/rss/",
        "category": "regional_south",
        "priority": "high"
    },
    {
        "name": "Комсомольская правда Ростов",
        "url": "https://www.rostov.kp.ru/rss/",
        "category": "regional_south",
        "priority": "medium"
    },
]

# Дальний Восток
FAR_EAST_SOURCES = [
    {
        "name": "VL.ru (Владивосток)",
        "url": "https://www.newsvl.ru/vlad/feed/",
        "category": "regional_fareast",
        "priority": "medium"
    },
]

# Федеральные СМИ
FEDERAL_SOURCES = [
    {
        "name": "РБК",
        "url": "https://rssexport.rbc.ru/rbcnews/news/20/full.rss",
        "category": "federal",
        "priority": "medium"
    },
    {
        "name": "ТАСС",
        "url": "https://tass.ru/rss/v2.xml",
        "category": "federal",
        "priority": "medium"
    },
    {
        "name": "Интерфакс",
        "url": "https://www.interfax.ru/rss.asp",
        "category": "federal",
        "priority": "medium"
    },
    {
        "name": "РИА Новости",
        "url": "https://ria.ru/export/rss2/archive/index.xml",
        "category": "federal",
        "priority": "low"
    },
]

# Отраслевые источники (ЖКХ, водоснабжение)
INDUSTRY_SOURCES = [
    {
        "name": "ТЭК ФМ",
        "url": "https://news.tek.fm/feed",
        "category": "industry_utilities",
        "priority": "high"
    },
]

# Тестовый источник
TEST_SOURCES = [
    {
        "name": "Тестовый сайт аварий",
        "url": "http://localhost:8000/feed.xml",
        "category": "test",
        "priority": "critical"
    },
]

# Собрать все источники
ALL_SOURCES = (
    TEST_SOURCES +
    NEWS_AGGREGATORS +
    OFFICIAL_SOURCES +
    MOSCOW_SOURCES +
    SPB_SOURCES +
    URAL_SOURCES +
    SIBERIA_SOURCES +
    VOLGA_SOURCES +
    SOUTH_SOURCES +
    FAR_EAST_SOURCES +
    FEDERAL_SOURCES +
    INDUSTRY_SOURCES
)

# Приоритетные источники (для быстрой проверки)
PRIORITY_SOURCES = [s for s in ALL_SOURCES if s.get("priority") in ["critical", "high"]]
