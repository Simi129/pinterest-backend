# app/models.py
from pydantic import BaseModel, HttpUrl
from typing import Optional
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

class PinAnalytics(BaseModel):
    """
    Модель аналитики пина
    """
    pin_id: str
    impressions: int
    saves: int
    clicks: int
    date: datetime

# ==================== Board Models ====================

class CreateBoardRequest(BaseModel):
    """
    Модель для создания доски
    """
    user_id: str
    name: str
    description: Optional[str] = ""
    privacy: Optional[str] = "PUBLIC"  # PUBLIC или SECRET

class UpdateBoardRequest(BaseModel):
    """
    Модель для обновления доски
    """
    user_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    privacy: Optional[str] = None