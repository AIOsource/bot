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
    
    RSS_SOURCES: List[dict] = [
        {"name": "Google", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "test"},
        {"name": "Яндекс ЖКХ", "url": "https://news.yandex.ru/housing_and_public_utilities.rss", "category": "aggregator"},
        {"name": "Яндекс Происшествия", "url": "https://news.yandex.ru/incident.rss", "category": "aggregator"},
        {"name": "Яндекс Москва", "url": "https://news.yandex.ru/Moscow/index.rss", "category": "aggregator"},
        {"name": "Рамблер Главное", "url": "https://news.rambler.ru/rss/head/", "category": "aggregator"},
        {"name": "Рамблер Происшествия", "url": "https://news.rambler.ru/rss/incidents/", "category": "aggregator"},
        {"name": "РБК Главное", "url": "https://rssexport.rbc.ru/rbcnews/news/20/full.rss", "category": "federal"},
        {"name": "ТАСС", "url": "https://tass.ru/rss/v2.xml", "category": "federal"},
        {"name": "Интерфакс", "url": "https://www.interfax.ru/rss.asp", "category": "federal"},
        {"name": "РИА Новости", "url": "https://ria.ru/export/rss2/archive/index.xml", "category": "federal"},
        {"name": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/main.xml", "category": "federal"},
        {"name": "Известия", "url": "https://iz.ru/xml/rss/all.xml", "category": "federal"},
        {"name": "Российская Газета", "url": "https://rg.ru/xml/index.xml", "category": "federal"},
        {"name": "Ведомости", "url": "https://www.vedomosti.ru/rss/news", "category": "federal"},
        {"name": "Лента.ру", "url": "https://lenta.ru/rss/news", "category": "federal"},
        {"name": "Газета.ру", "url": "https://www.gazeta.ru/export/rss/lenta.xml", "category": "federal"},
        {"name": "МЧС России", "url": "https://mchs.gov.ru/feed", "category": "emergency"},
        {"name": "МЧС Москва", "url": "https://moscow.mchs.gov.ru/feed", "category": "emergency"},
        {"name": "МЧС СПБ", "url": "https://78.mchs.gov.ru/feed", "category": "emergency"},
        {"name": "Минстрой РФ", "url": "https://minstroyrf.gov.ru/upload/rss/news.xml", "category": "gov"},
        {"name": "Росприроднадзор", "url": "https://rpn.gov.ru/rss/", "category": "gov"},
        {"name": "ТЭК ФМ", "url": "https://news.tek.fm/feed", "category": "industry"},
        {"name": "ЖКХ Портал", "url": "https://www.gkh.ru/rss/news", "category": "industry"},
        {"name": "Коммунальщик", "url": "https://xn--80aaahlarkgbcfl6a6k.xn--p1ai/feed/", "category": "industry"},
        {"name": "Энергетика и Промышленность", "url": "https://www.eprussia.ru/rss/news.xml", "category": "industry"},
        {"name": "Водоснабжение Украины (СНГ)", "url": "http://vodokanal-magazine.ru/feed/", "category": "industry"},
        {"name": "Новости Энергетики", "url": "https://novostienergetiki.ru/feed/", "category": "industry"},
        {"name": "ЖКХ Ньюс", "url": "https://gkhnews.ru/feed/", "category": "industry"},
        {"name": "Elec.ru", "url": "https://www.elec.ru/feed/news/", "category": "industry"},
        {"name": "Энергосовет", "url": "https://energosovet.ru/rss.php", "category": "industry"},
        {"name": "Теплоэнергетика", "url": "https://www.rosteplo.ru/rss.php", "category": "industry"},
        {"name": "МК Москва", "url": "https://www.mk.ru/rss/index.xml", "category": "moscow"},
        {"name": "Москва 24", "url": "https://www.m24.ru/rss.xml", "category": "moscow"},
        {"name": "Вечерняя Москва", "url": "https://vm.ru/rss/news.xml", "category": "moscow"},
        {"name": "Московская правда", "url": "https://mospravda.ru/rss/", "category": "moscow"},
        {"name": "Подмосковье сегодня", "url": "https://mosregtoday.ru/feed/", "category": "moscow"},
        {"name": "Регнам Центр", "url": "https://regnum.ru/rss/news", "category": "center"},
        {"name": "Вести Подмосковья", "url": "https://vmo24.ru/rss", "category": "moscow"},
        {"name": "РИАМО", "url": "https://riamo.ru/rss", "category": "moscow"},
        {"name": "Тульская служба новостей", "url": "https://www.tsn24.ru/rss/", "category": "center"},
        {"name": "Курские известия", "url": "https://kursk-izvestia.ru/rss", "category": "center"},
        {"name": "Фонтанка", "url": "https://www.fontanka.ru/fontanka.rss", "category": "spb"},
        {"name": "Деловой Петербург", "url": "https://www.dp.ru/RSS", "category": "spb"},
        {"name": "47 новостей (Ленобласть)", "url": "https://47news.ru/rss/", "category": "spb"},
        {"name": "Невские Новости", "url": "https://nevnov.ru/rss/all.xml", "category": "spb"},
        {"name": "Псковская Лента", "url": "https://pln-pskov.ru/export/rss.xml", "category": "nw"},
        {"name": "Калининград.Ru", "url": "https://kgd.ru/rss", "category": "nw"},
        {"name": "Новый Калининград", "url": "https://www.newkaliningrad.ru/rss/", "category": "nw"},
        {"name": "СеверПост (Мурманск)", "url": "https://severpost.ru/rss/", "category": "nw"},
        {"name": "КомиИнформ", "url": "https://komiinform.ru/rss/news", "category": "nw"},
        {"name": "Бумага (СПб)", "url": "https://paperpaper.ru/feed/", "category": "spb"},
        {"name": "Е1.ру (Екатеринбург)", "url": "https://www.e1.ru/text/rss.xml", "category": "ural"},
        {"name": "URA.news", "url": "https://ura.news/feeds/rss", "category": "ural"},
        {"name": "Znak.com", "url": "https://www.znak.com/rss", "category": "ural"},
        {"name": "66.ru", "url": "https://66.ru/rss/", "category": "ural"},
        {"name": "74.ru (Челябинск)", "url": "https://74.ru/text/rss.xml", "category": "ural"},
        {"name": "59.ru (Пермь)", "url": "https://59.ru/text/rss.xml", "category": "ural"},
        {"name": "72.ru (Тюмень)", "url": "https://72.ru/text/rss.xml", "category": "ural"},
        {"name": "Правда УрФО", "url": "https://pravdaurfo.ru/feed", "category": "ural"},
        {"name": "Накануне.RU", "url": "https://www.nakanune.ru/rss/", "category": "ural"},
        {"name": "УралПолит", "url": "https://uralpolit.ru/rss", "category": "ural"},
        {"name": "НГС (Новосибирск)", "url": "https://news.ngs.ru/rss/", "category": "siberia"},
        {"name": "Сиб.фм", "url": "https://sib.fm/rss", "category": "siberia"},
        {"name": "Тайга.инфо", "url": "https://tayga.info/rss", "category": "siberia"},
        {"name": "Алтапресс", "url": "https://altapress.ru/rss", "category": "siberia"},
        {"name": "Омск Здесь", "url": "https://omskzdes.ru/rss.xml", "category": "siberia"},
        {"name": "Томский Обзор", "url": "https://obzor.city/rss", "category": "siberia"},
        {"name": "Иркутск Сегодня", "url": "https://irkutsk.today/feed/", "category": "siberia"},
        {"name": "Наш Красноярский край", "url": "https://gnkk.ru/feed/", "category": "siberia"},
        {"name": "Байкал Daily", "url": "https://www.baikal-daily.ru/rss.php", "category": "siberia"},
        {"name": "НГС54", "url": "https://ngs54.ru/text/news/rss.xml", "category": "siberia"},
        {"name": "Юга.ру", "url": "https://www.yuga.ru/news/rss/", "category": "south"},
        {"name": "161.ру (Ростов)", "url": "https://161.ru/text/rss/", "category": "south"},
        {"name": "Кавказский Узел", "url": "https://www.kavkaz-uzel.eu/feed.rss", "category": "south"},
        {"name": "Блокнот Краснодар", "url": "https://bloknot-krasnodar.ru/rss/", "category": "south"},
        {"name": "Кубань 24", "url": "https://kuban24.tv/feed", "category": "south"},
        {"name": "Волгоградская Правда", "url": "https://vpravda.ru/feed/", "category": "south"},
        {"name": "Крым 24", "url": "https://crimea24.tv/feed/", "category": "south"},
        {"name": "Сочи Стрим", "url": "https://sochistream.ru/feed", "category": "south"},
        {"name": "Ставропольская правда", "url": "https://stapravda.ru/rss.xml", "category": "south"},
        {"name": "Грозный Информ", "url": "https://www.grozny-inform.ru/rss/", "category": "south"},
        {"name": "Бизнес-Онлайн (Казань)", "url": "https://www.business-gazeta.ru/rss/", "category": "volga"},
        {"name": "НН.Ру (Нижний)", "url": "https://www.nn.ru/rss.php", "category": "volga"},
        {"name": "Волга Ньюс", "url": "https://volga.news/rss", "category": "volga"},
        {"name": "Уфа1 (Башкирия)", "url": "https://ufa1.ru/text/rss/", "category": "volga"},
        {"name": "Татар-информ", "url": "https://www.tatar-inform.ru/rss", "category": "volga"},
        {"name": "Первый Самарский", "url": "https://1samara.ru/feed/", "category": "volga"},
        {"name": "ПензаИнформ", "url": "https://www.penzainform.ru/rss/news.xml", "category": "volga"},
        {"name": "Саратов 24", "url": "https://saratov24.tv/rss/", "category": "volga"},
        {"name": "Марийская правда", "url": "https://www.marpravda.ru/rss/", "category": "volga"},
        {"name": "Про Город (Чувашия)", "url": "https://pg21.ru/rss", "category": "volga"},
        {"name": "VL.ru (Владивосток)", "url": "https://www.newsvl.ru/vlad/feed/", "category": "fareast"},
        {"name": "ДВ.Лэнд", "url": "https://dv.land/rss", "category": "fareast"},
        {"name": "Восток-Медиа", "url": "https://vostokmedia.com/rss", "category": "fareast"},
        {"name": "Амур.инфо", "url": "https://www.amur.info/rss", "category": "fareast"},
        {"name": "Сахалин.Инфо", "url": "https://sakhalin.info/rss", "category": "fareast"},
        {"name": "Якутия 24", "url": "https://yk24.ru/feed/", "category": "fareast"},
        {"name": "Хабаровский край", "url": "https://khabkrai.ru/events/news/rss/", "category": "fareast"},
        {"name": "ПримаМедиа", "url": "https://primamedia.ru/export/rss.xml", "category": "fareast"},
        {"name": "Магаданская правда", "url": "https://magadanpravda.ru/feed", "category": "fareast"},
        {"name": "Камчатка-Информ", "url": "https://kamchatinfo.com/rss/", "category": "fareast"},
    ]
    
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
