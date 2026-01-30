import json
import logging
from typing import Optional, List, Dict
from datetime import datetime
from openai import OpenAI
from models import NewsArticle, FilteredEvent
from config import config
from database import db

logger = logging.getLogger(__name__)


class AIFilter:
    def __init__(self):
        self.client = OpenAI(api_key=config.PERPLEXITY_API_KEY, base_url=config.PERPLEXITY_API_BASE)
        self.model = config.PERPLEXITY_MODEL
        self.keywords = config.KEYWORDS
        self.threshold = config.RELEVANCE_THRESHOLD
    
    def filter_article(self, article: NewsArticle) -> Optional[FilteredEvent]:
        try:
            prompt = self._create_analysis_prompt(article)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты аналитик новостей. Отвечай только в формате JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500
            )
            
            result = self._parse_ai_response(response)
            
            if response and response.choices:
                raw_response = response.choices[0].message.content
                logger.info(f"📝 Raw AI response:\n{raw_response[:500]}")
            
            if not result:
                logger.warning(f"Failed to parse AI response for article: {article.title}")
                return None
            
            logger.info(f"AI analyzed: {article.title[:50]}...")
            logger.info(f"  Score: {result['relevance_score']:.2f} | Threshold: {self.threshold}")
            logger.info(f"  Category: {result.get('category', 'unknown')}")
            logger.info(f"  Reasoning: {result.get('reasoning', 'no reasoning')[:100]}")
            
            if result['relevance_score'] < self.threshold:
                logger.info(f"  💤 REJECTED (below threshold)")
                return None
            
            logger.info(f"  ✅ ACCEPTED (above threshold)")
            
            event = FilteredEvent(
                article_id=article.id,
                title=article.title,
                url=article.url,
                relevance_score=result['relevance_score'],
                key_points=[result.get('reasoning', '')],
                category=result.get('event_type', 'другое'),
                reasoning=result.get('reasoning', ''),
                filtered_at=datetime.now()
            )
            
            event.reasoning = f"[{result.get('region', 'не указан')}] {result.get('object', 'не указан')} | Насосы: {result.get('needs_pumps', 'нет')} | Срочность: {result.get('urgency', 1)}/5 | {result.get('reasoning', '')}"
            
            event_dict = event.model_dump()
            event_dict['filtered_at'] = event_dict['filtered_at'].isoformat()
            event_id = db.save_filtered_event(event_dict)
            
            logger.info(f"Filtered relevant article: {article.title} (score: {result['relevance_score']:.2f})")
            return event
            
        except Exception as e:
            logger.error(f"Error filtering article {article.title}: {e}")
            return None
    
    def _create_analysis_prompt(self, article: NewsArticle) -> str:
        prompt = f"""
Ты - аналитик аварий ЖКХ. Твоя задача - найти события с потребностью в НАСОСНОМ ОБОРУДОВАНИИ.

ВХОДНЫЕ ДАННЫЕ:
Заголовок: {article.title}
Источник: {article.source}
Текст: {article.content[:1500]}

ЗАПРЕТ (ИГНОРИРОВАТЬ):
❌ Закупки, тендеры, лоты
❌ Цены, маржинальность, финансы
❌ Внутренние данные компаний
Если новость об этом -> верни needs_pumps="нет" и urgency=0.

ПРАВИЛА АНАЛИЗА:
1. Ищи: аварии, прорывы, остановки, срочные ремонты, износ, замены.
2. Потребность в насосах:
   - ЕСТЬ ("да"), если: прорыв трубы, затопление, остановка КНС/ВНС.
   - НЕТ ("нет"), если: плановое отключение, благоустройство.
3. Срочность (1-5):
   - 5: Критическая авария, сотни людей без воды/тепла, ЧС.
   - 3-4: Серьезная поломка, нужен срочный ремонт.
   - 1-2: Плановые работы, мелкие утечки.

ФОРМАТ ОТВЕТА (JSON):
{{
  "event_type": "авария" | "остановка" | "ремонт" | "другое",
  "needs_pumps": "да" | "нет",
  "urgency": 1-5,
  "comment": "1 предложение",
  "region": "Регион или 'не указан'",
  "object": "Объект или 'не указан'",
  "relevance_score": 0.0-1.0
}}
"""
        return prompt
    
    def _parse_ai_response(self, response) -> Optional[Dict]:
        try:
            content = response.choices[0].message.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            result = json.loads(content)
            if 'relevance_score' not in result:
                return None
            result['relevance_score'] = max(0.0, min(1.0, float(result['relevance_score'])))
            return result
        except (json.JSONDecodeError, IndexError, KeyError, ValueError) as e:
            logger.error(f"Error parsing AI response: {e}")
            return None


ai_filter = AIFilter()
