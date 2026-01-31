from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    id: str = Field(description="Unique identifier")
    title: str = Field(description="Article title")
    url: str = Field(description="Article URL")
    content: str = Field(description="Article content")
    source: str = Field(description="Source name")
    category: str = Field(description="Source category")
    published_at: Optional[datetime] = Field(default=None)
    collected_at: datetime = Field(default_factory=datetime.now)
    content_hash: Optional[str] = Field(default=None, description="Hash for deduplication")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class FilteredEvent(BaseModel):
    article_id: str = Field(description="Reference to original article")
    title: str = Field(description="Article title")
    url: str = Field(description="Article URL")
    relevance_score: float = Field(description="AI relevance score (0.0-1.0)")
    category: str = Field(description="Event category: accident | outage | repair | other")
    urgency: int = Field(description="Urgency level 1-5")
    object: str = Field(description="Affected object: water | heat | industrial | unknown")
    why: str = Field(description="Short explanation")
    action: str = Field(description="Action: call | watch | ignore")
    filtered_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class TelegramSignal(BaseModel):
    event_id: str = Field(description="Reference to filtered event")
    title: str = Field(description="Signal title")
    message: str = Field(description="Formatted message")
    url: str = Field(description="Source URL")
    priority: str = Field(description="Priority level")
    sent_at: Optional[datetime] = Field(default=None)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
