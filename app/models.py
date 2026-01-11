# app/models.py
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

class PostCreate(BaseModel):
    """
    Модель для создания поста
    """
    board_id: str
    image_url: HttpUrl
    title: str
    description: Optional[str] = ""
    link: Optional[HttpUrl] = None
    scheduled_at: Optional[datetime] = None
    user_id: str
    keywords: Optional[List[str]] = None  # Добавили поддержку ключевых слов

class PostResponse(BaseModel):
    """
    Модель ответа после создания поста
    """
    id: str
    status: str
    scheduled_at: Optional[datetime] = None
    pinterest_pin_id: Optional[str] = None
    created_at: datetime

class PublishNowRequest(BaseModel):
    """
    Модель для немедленной публикации
    """
    board_id: str
    image_url: HttpUrl
    title: str
    description: Optional[str] = ""
    link: Optional[HttpUrl] = None
    user_id: str
    keywords: Optional[List[str]] = None  # Добавили ключевые слова

class SchedulePostRequest(BaseModel):
    """
    Модель для запланированной публикации
    """
    board_id: str
    image_url: HttpUrl
    title: str
    description: Optional[str] = ""
    link: Optional[HttpUrl] = None
    scheduled_at: datetime
    user_id: str
    keywords: Optional[List[str]] = None  # Добавили ключевые слова

class PinAnalytics(BaseModel):
    """
    Модель аналитики пина
    """
    pin_id: str
    impressions: int
    saves: int
    clicks: int
    date: datetime

class AccountAnalyticsResponse(BaseModel):
    """
    Модель ответа аналитики аккаунта
    """
    success: bool
    analytics: Dict
    period: Dict

class PinAnalyticsResponse(BaseModel):
    """
    Модель ответа аналитики пина
    """
    success: bool
    analytics: Dict
    pin_id: str

class BoardAnalyticsResponse(BaseModel):
    """
    Модель ответа аналитики доски
    """
    success: bool
    analytics: Dict
    board_id: str

class CreateBoardRequest(BaseModel):
    """
    Модель для создания доски
    """
    user_id: str
    name: str
    description: Optional[str] = ""
    privacy: Optional[str] = "PUBLIC"

class UpdateBoardRequest(BaseModel):
    """
    Модель для обновления доски
    """
    user_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    privacy: Optional[str] = None