# app/database.py
from supabase import create_client, Client
import os
from typing import Optional, Dict, List
from datetime import datetime

# Инициализация Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def create_post(post_data: Dict) -> Dict:
    """
    Создать пост в базе данных
    """
    response = supabase.table("posts").insert(post_data).execute()
    return response.data[0] if response.data else None

def get_post(post_id: str) -> Optional[Dict]:
    """
    Получить пост по ID
    """
    response = supabase.table("posts").select("*").eq("id", post_id).execute()
    return response.data[0] if response.data else None

def update_post_status(post_id: str, status: str, pinterest_pin_id: Optional[str] = None) -> Dict:
    """
    Обновить статус поста
    """
    update_data = {"status": status}
    if pinterest_pin_id:
        update_data["pinterest_pin_id"] = pinterest_pin_id
    
    response = supabase.table("posts").update(update_data).eq("id", post_id).execute()
    return response.data[0] if response.data else None

def get_scheduled_posts() -> List[Dict]:
    """
    Получить все запланированные посты, которые нужно опубликовать
    """
    now = datetime.utcnow().isoformat()
    response = (
        supabase.table("posts")
        .select("*")
        .eq("status", "scheduled")
        .lte("scheduled_at", now)
        .execute()
    )
    return response.data

def get_user_posts(user_id: str, limit: int = 50) -> List[Dict]:
    """
    Получить посты пользователя
    """
    response = (
        supabase.table("posts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data