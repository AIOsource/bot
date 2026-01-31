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
        self.threshold = config.LLM_RELEVANCE_THRESHOLD
        
        # Stage 2 Configs
        self.positive_keywords = config.KEYWORDS_POSITIVE
        self.negative_keywords = config.KEYWORDS_NEGATIVE
        self.weights = config.SCORE_WEIGHTS
        self.score_threshold = config.KEYWORD_SCORE_THRESHOLD
    
    def filter_article(self, article: NewsArticle) -> Optional[FilteredEvent]:
        try:
            # 1. Pre-filtering (Weighted Scoring)
            keyword_score = self._calculate_keyword_score(article.title + " " + article.content)
            
            if keyword_score < self.score_threshold:
                # logger.debug(f"Skipping {article.title[:30]}... (Score: {keyword_score})")
                return None
                
            logger.info(f"🔎 Analyzing (Score {keyword_score}): {article.title[:50]}...")

            # 2. LLM Analysis
            prompt = self._create_analysis_prompt(article)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты аналитик инцидентов ЖКХ. Твоя задача — классифицировать события и возвращать JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            result = self._parse_ai_response(response)
            
            if not result:
                logger.warning(f"Failed to parse AI response for: {article.title}")
                return None
            
            # 3. Post-processing & Validation
            relevance = result.get('relevance', 0.0)
            urgency = result.get('urgency', 1)
            
            if relevance < self.threshold:
                logger.info(f"  💤 REJECTED (Relevance {relevance:.2f} < {self.threshold})")
                return None
                
            logger.info(f"  ✅ ACCEPTED (Relevance {relevance:.2f} | Urgency {urgency})")
            
            event = FilteredEvent(
                article_id=article.id,
                title=article.title,
                url=article.url,
                relevance_score=relevance,
                category=result.get('event_type', 'other'),
                urgency=urgency,
                object=result.get('object', 'unknown'),
                why=result.get('why', 'No explanation'),
                action=result.get('action', 'ignore'),
                filtered_at=datetime.now()
            )
            
            # Save raw 'why' as reasoning for backward compatibility if needed, or just use 'why'
            event.reasoning = f"{event.why} (Action: {event.action})"
            
            event_dict = event.model_dump()
            event_dict['filtered_at'] = event_dict['filtered_at'].isoformat()
            db.save_filtered_event(event_dict)
            
            return event
            
        except Exception as e:
            logger.error(f"Error filtering article {article.title}: {e}")
            return None

    def _calculate_keyword_score(self, text: str) -> int:
        score = 0
        text_lower = text.lower()
        
        # Positive weights
        for word in self.positive_keywords:
            if word in text_lower:
                # Basic logic: if keyword found, add points based on category
                # For simplicity, we'll try to map keywords to categories or just use a default positive weight
                if word in ["авария", "прорыв", "остановка"]:
                    score += self.weights.get("accident", 3)
                elif word in ["ремонт", "замена"]:
                    score += self.weights.get("repair", 2)
                elif word in ["водоканал", "котельная", "насосная"]:
                    score += self.weights.get("infra", 4)
                elif word in ["цех", "агрегат"]:
                    score += self.weights.get("industry", 2)
                else:
                    score += 1 # Default positive
        
        # Negative weights
        for word in self.negative_keywords:
            if word in text_lower:
                score += self.weights.get("negative", -5)
        
        return score
    
    def _create_analysis_prompt(self, article: NewsArticle) -> str:
        return f"""
Проанализируй новость и классифицируй её для системы мониторинга инцидентов ЖКХ.

ВХОДНЫЕ ДАННЫЕ:
Заголовок: {article.title}
Источник: {article.source}
Текст: {article.content[:2000]}

ПРАВИЛА:
1. Тип события (event_type):
   - accident: авария, прорыв, утечка, поломка, остановка, выход из строя
   - outage: отключение света/воды/тепла (без явной аварии)
   - repair: ремонт, замена, модернизация, работы
   - other: учения, ДТП, пожары (не ЖКХ), криминал, прочее

2. Сфера (object):
   - water: водоснабжение, канализация, насосы
   - heat: отопление, котельные, теплосети
   - industrial: заводы, производство, агрегаты
   - unknown: не ясно

3. Срочность (urgency 1-5):
   - 1: Плановые, неважные
   - 3: Важные (идут работы, отключения)
   - 5: ЧП, экстренные, массовые отключения

4. Релевантность (relevance 0.0-1.0):
   - 0.8-1.0: Высокая (Аварии, реальные инциденты)
   - 0.6-0.7: Средняя (Ремонты, отключения)
   - <0.6: Низкая (Мусор, не относится к теме)

5. Действие (action):
   - call: Если relevance >= 0.6 И urgency >= 3
   - watch: Если relevance >= 0.6 И urgency < 3
   - ignore: Иначе

ФОРМАТ ОТВЕТА (JSON):
{{
  "event_type": "accident|outage|repair|other",
  "relevance": float,
  "urgency": int,
  "object": "water|heat|industrial|unknown",
  "why": "Одна фраза - причина важности",
  "action": "call|watch|ignore"
}}
"""
    
    def _parse_ai_response(self, response) -> Optional[Dict]:
        try:
            content = response.choices[0].message.content.strip()
            # Clean markdown
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
                
            result = json.loads(content)
            
            # Validate essential fields
            required = ['event_type', 'relevance', 'urgency']
            if not all(k in result for k in required):
                logger.warning(f"AI response missing fields: {result.keys()}")
                return None
                
            result['relevance'] = float(result['relevance'])
            return result
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None


ai_filter = AIFilter()
