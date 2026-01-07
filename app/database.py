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

# ==================== Pinterest Connections ====================

def create_pinterest_connection(connection_data: Dict) -> Optional[Dict]:
    """
    Создать или обновить Pinterest подключение
    """
    try:
        # Проверяем есть ли уже подключение
        existing = supabase.table("pinterest_connections")\
            .select("*")\
            .eq("user_id", connection_data["user_id"])\
            .execute()
        
        if existing.data:
            # Обновляем существующее
            response = supabase.table("pinterest_connections")\
                .update(connection_data)\
                .eq("user_id", connection_data["user_id"])\
                .execute()
        else:
            # Создаём новое
            response = supabase.table("pinterest_connections")\
                .insert(connection_data)\
                .execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating/updating Pinterest connection: {e}")
        raise

def get_pinterest_connection(user_id: str) -> Optional[Dict]:
    """
    Получить Pinterest подключение пользователя
    """
    try:
        response = supabase.table("pinterest_connections")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting Pinterest connection: {e}")
        return None

def delete_pinterest_connection(user_id: str) -> bool:
    """
    Удалить Pinterest подключение
    """
    try:
        supabase.table("pinterest_connections")\
            .delete()\
            .eq("user_id", user_id)\
            .execute()
        return True
    except Exception as e:
        print(f"Error deleting Pinterest connection: {e}")
        raise

def update_pinterest_token(
    user_id: str, 
    access_token: str, 
    refresh_token: Optional[str] = None, 
    expires_at: Optional[datetime] = None
) -> Optional[Dict]:
    """
    Обновить токены Pinterest подключения
    """
    try:
        update_data = {
            "access_token": access_token,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if refresh_token:
            update_data["refresh_token"] = refresh_token
        
        if expires_at:
            update_data["expires_at"] = expires_at.isoformat()
        
        response = supabase.table("pinterest_connections")\
            .update(update_data)\
            .eq("user_id", user_id)\
            .execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating Pinterest token: {e}")
        raise

# ==================== Posts ====================

def create_post(post_data: Dict) -> Optional[Dict]:
    """
    Создать пост в базе данных
    """
    try:
        response = supabase.table("posts")\
            .insert(post_data)\
            .execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating post: {e}")
        raise

def get_post(post_id: str) -> Optional[Dict]:
    """
    Получить пост по ID
    """
    try:
        response = supabase.table("posts")\
            .select("*")\
            .eq("id", post_id)\
            .execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting post: {e}")
        return None

def update_post(post_id: str, update_data: Dict) -> Optional[Dict]:
    """
    Обновить пост
    """
    try:
        response = supabase.table("posts")\
            .update(update_data)\
            .eq("id", post_id)\
            .execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating post: {e}")
        raise

def update_post_status(
    post_id: str, 
    status: str, 
    pinterest_pin_id: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[Dict]:
    """
    Обновить статус поста
    """
    try:
        update_data = {"status": status}
        
        if pinterest_pin_id:
            update_data["pinterest_pin_id"] = pinterest_pin_id
        
        if error_message:
            update_data["error_message"] = error_message
        
        response = supabase.table("posts")\
            .update(update_data)\
            .eq("id", post_id)\
            .execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating post status: {e}")
        raise

def delete_post(post_id: str) -> bool:
    """
    Удалить пост
    """
    try:
        supabase.table("posts")\
            .delete()\
            .eq("id", post_id)\
            .execute()
        return True
    except Exception as e:
        print(f"Error deleting post: {e}")
        raise

def get_user_posts(
    user_id: str, 
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    Получить посты пользователя
    """
    try:
        query = supabase.table("posts")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)
        
        if status:
            query = query.eq("status", status)
        
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error getting user posts: {e}")
        return []

def get_scheduled_posts(before_datetime: Optional[datetime] = None) -> List[Dict]:
    """
    Получить все запланированные посты, которые нужно опубликовать
    """
    try:
        now = before_datetime or datetime.utcnow()
        
        response = supabase.table("posts")\
            .select("*")\
            .eq("status", "scheduled")\
            .lte("scheduled_at", now.isoformat())\
            .execute()
        
        return response.data
    except Exception as e:
        print(f"Error getting scheduled posts: {e}")
        return []

def get_user_stats(user_id: str) -> Optional[Dict]:
    """
    Получить статистику постов пользователя
    """
    try:
        response = supabase.rpc("get_user_stats", {"p_user_id": user_id}).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user stats: {e}")
        # Fallback: считаем вручную
        try:
            posts = get_user_posts(user_id, limit=1000)
            
            stats = {
                "total_posts": len(posts),
                "total_published": len([p for p in posts if p["status"] == "published"]),
                "total_scheduled": len([p for p in posts if p["status"] == "scheduled"]),
                "total_failed": len([p for p in posts if p["status"] == "failed"]),
                "last_published_at": None
            }
            
            published_posts = [p for p in posts if p["status"] == "published" and p.get("published_at")]
            if published_posts:
                stats["last_published_at"] = max(p["published_at"] for p in published_posts)
            
            return stats
        except:
            return None

# ==================== Pin Analytics ====================

def save_pin_analytics(analytics_data: Dict) -> Optional[Dict]:
    """
    Сохранить аналитику пина
    """
    try:
        # Проверяем существует ли запись для этой даты
        existing = supabase.table("pin_analytics")\
            .select("*")\
            .eq("post_id", analytics_data["post_id"])\
            .eq("date", analytics_data["date"])\
            .execute()
        
        if existing.data:
            # Обновляем
            response = supabase.table("pin_analytics")\
                .update(analytics_data)\
                .eq("post_id", analytics_data["post_id"])\
                .eq("date", analytics_data["date"])\
                .execute()
        else:
            # Создаём новую
            response = supabase.table("pin_analytics")\
                .insert(analytics_data)\
                .execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error saving pin analytics: {e}")
        raise

def get_post_analytics(post_id: str, days: int = 30) -> List[Dict]:
    """
    Получить аналитику для поста за последние N дней
    """
    try:
        from_date = (datetime.utcnow() - timedelta(days=days)).date()
        
        response = supabase.table("pin_analytics")\
            .select("*")\
            .eq("post_id", post_id)\
            .gte("date", from_date.isoformat())\
            .order("date", desc=True)\
            .execute()
        
        return response.data
    except Exception as e:
        print(f"Error getting post analytics: {e}")
        return []

def get_user_analytics_summary(user_id: str, days: int = 30) -> Dict:
    """
    Получить сводную аналитику для пользователя
    """
    try:
        from_date = (datetime.utcnow() - timedelta(days=days)).date()
        
        # Получаем все посты пользователя
        posts = get_user_posts(user_id, status="published", limit=1000)
        post_ids = [p["id"] for p in posts]
        
        if not post_ids:
            return {
                "total_impressions": 0,
                "total_saves": 0,
                "total_clicks": 0,
                "total_outbound_clicks": 0,
                "total_pin_clicks": 0,
                "period_days": days
            }
        
        # Получаем аналитику
        response = supabase.table("pin_analytics")\
            .select("*")\
            .in_("post_id", post_ids)\
            .gte("date", from_date.isoformat())\
            .execute()
        
        analytics = response.data
        
        # Суммируем
        summary = {
            "total_impressions": sum(a.get("impressions", 0) for a in analytics),
            "total_saves": sum(a.get("saves", 0) for a in analytics),
            "total_clicks": sum(a.get("clicks", 0) for a in analytics),
            "total_outbound_clicks": sum(a.get("outbound_clicks", 0) for a in analytics),
            "total_pin_clicks": sum(a.get("pin_clicks", 0) for a in analytics),
            "period_days": days
        }
        
        return summary
    except Exception as e:
        print(f"Error getting user analytics summary: {e}")
        return {
            "total_impressions": 0,
            "total_saves": 0,
            "total_clicks": 0,
            "total_outbound_clicks": 0,
            "total_pin_clicks": 0,
            "period_days": days
        }

# Импорт для аналитики
from datetime import timedelta