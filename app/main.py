# app/main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from typing import Optional
import os
from datetime import datetime, timedelta
import traceback

from app.models import (
    PostCreate, 
    PostResponse, 
    PublishNowRequest, 
    SchedulePostRequest,
    CreateBoardRequest,
    UpdateBoardRequest
)
from app.database import (
    get_pinterest_connection,
    create_pinterest_connection,
    delete_pinterest_connection,
    create_post,
    update_post_status,
    get_user_posts,
    get_user_stats,
    get_post_analytics,
    get_user_analytics_summary,
    save_oauth_state,
    get_oauth_state,
    cleanup_old_oauth_states
)
from app.pinterest import get_pinterest_client
from app.oauth import (
    get_pinterest_auth_url,
    exchange_code_for_token,
    refresh_pinterest_token
)

app = FastAPI(title="Pinterest Automation API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Кеш для статусов ====================
status_cache = {}
CACHE_TTL = 300  # 5 минут

def get_cached_status(user_id: str) -> Optional[dict]:
    """Получить статус из кеша"""
    if user_id in status_cache:
        cached_data, timestamp = status_cache[user_id]
        if datetime.utcnow().timestamp() - timestamp < CACHE_TTL:
            return cached_data
    return None

def set_cached_status(user_id: str, status: dict):
    """Сохранить статус в кеш"""
    status_cache[user_id] = (status, datetime.utcnow().timestamp())

def clear_cached_status(user_id: str):
    """Очистить статус из кеша"""
    if user_id in status_cache:
        del status_cache[user_id]

# ==================== Health Check ====================

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Pinterest Automation API"}

@app.get("/health")
def health_check():
    """Health check для uptime мониторинга"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_size": len(status_cache)
    }

# ==================== OAuth ====================

@app.get("/auth/pinterest")
def pinterest_auth(user_id: str):
    """
    Начать OAuth процесс для Pinterest
    """
    try:
        auth_url, state = get_pinterest_auth_url()
        
        # Сохраняем state в БД
        from app.database import save_oauth_state
        save_oauth_state(state, user_id)
        
        return RedirectResponse(url=auth_url)
    except Exception as e:
        print(f"Error initiating Pinterest auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/callback")
def pinterest_callback(code: str, state: str):
    """
    Обработка callback от Pinterest OAuth
    """
    try:
        # Проверяем state и получаем user_id
        user_id = get_oauth_state(state)
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid state")
        
        # Обмениваем code на access token (redirect_uri не нужен, берется из env)
        token_data = exchange_code_for_token(code)
        
        # Получаем информацию о пользователе Pinterest
        client = get_pinterest_client(token_data["access_token"])
        user_info = client.get_user_info()
        
        # Сохраняем подключение в БД
        connection_data = {
            "user_id": user_id,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "pinterest_user_id": user_info.get("username", ""),
            "pinterest_username": user_info.get("username", ""),
            "expires_at": (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat()
        }
        
        create_pinterest_connection(connection_data)
        
        # Очищаем кеш для этого пользователя
        clear_cached_status(user_id)
        
        # Редирект на фронтенд
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/dashboard?pinterest_connected=true")
    
    except Exception as e:
        print(f"Error in Pinterest callback: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(url=f"{frontend_url}/dashboard?error=connection_failed")

@app.get("/auth/pinterest/status")
def get_pinterest_connection_status(user_id: str = Query(...)):
    """
    Проверить статус подключения Pinterest (С КЕШИРОВАНИЕМ!)
    """
    try:
        # Проверяем кеш
        cached = get_cached_status(user_id)
        if cached:
            print(f"✅ Cache hit for user {user_id}")
            return cached
        
        print(f"⏱️ Cache miss, fetching from DB for user {user_id}")
        
        # Получаем из БД
        connection = get_pinterest_connection(user_id)
        
        if connection and connection.get("access_token"):
            result = {
                "connected": True,
                "pinterest_username": connection.get("pinterest_username", "Unknown"),
                "pinterest_user_id": connection.get("pinterest_user_id", "")
            }
        else:
            result = {"connected": False}
        
        # Сохраняем в кеш
        set_cached_status(user_id, result)
        
        return result
    
    except Exception as e:
        print(f"❌ Error checking Pinterest status: {e}")
        # Возвращаем дефолтный ответ при ошибке
        return {"connected": False}

@app.delete("/auth/pinterest/disconnect")
def disconnect_pinterest(user_id: str = Query(...)):
    """
    Отключить Pinterest аккаунт
    """
    try:
        delete_pinterest_connection(user_id)
        clear_cached_status(user_id)
        return {"success": True, "message": "Pinterest disconnected"}
    except Exception as e:
        print(f"Error disconnecting Pinterest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Boards ====================

@app.get("/api/boards")
def get_boards(user_id: str = Query(...)):
    """
    Получить список досок пользователя
    """
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        boards = client.get_boards()
        
        return boards
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/boards/create")
def create_board(request: CreateBoardRequest):
    """
    Создать новую доску
    """
    try:
        print(f"🔍 ===== CREATE BOARD REQUEST DEBUG =====")
        print(f"   user_id: {request.user_id}")
        print(f"   name: '{request.name}'")
        print(f"   description: '{request.description}'")
        print(f"   privacy: '{request.privacy}'")
        
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        print(f"🔑 Connection found, access_token preview: {connection['access_token'][:30]}...")
        
        client = get_pinterest_client(connection["access_token"])
        
        # Логируем точные данные, которые отправляем в Pinterest
        print(f"📤 Sending to Pinterest API:")
        print(f"   name: '{request.name}'")
        print(f"   description: '{request.description or ''}'")
        print(f"   privacy: '{request.privacy or 'PUBLIC'}'")
        
        board = client.create_board(
            name=request.name,
            description=request.description or "",
            privacy=request.privacy or "PUBLIC"
        )
        
        print(f"✅ Board created successfully: {request.name}")
        
        return board
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating board: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/boards/{board_id}")
def update_board(board_id: str, request: UpdateBoardRequest):
    """
    Обновить доску
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        board = client.update_board(
            board_id=board_id,
            name=request.name,
            description=request.description,
            privacy=request.privacy
        )
        
        return board
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/boards/{board_id}")
def delete_board(board_id: str, user_id: str = Query(...)):
    """
    Удалить доску
    """
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        client.delete_board(board_id)
        
        return {"success": True, "message": "Board deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Publish Now ====================

@app.post("/api/publish-now")
def publish_now(request: PublishNowRequest):
    """
    Немедленно опубликовать пин
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        # Создаем пост в БД
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "image_url": str(request.image_url),
            "title": request.title,
            "description": request.description or "",
            "link": str(request.link) if request.link else None,
            "status": "publishing",
            "created_at": datetime.utcnow().isoformat()
        }
        
        post = create_post(post_data)
        
        # Публикуем в Pinterest
        client = get_pinterest_client(connection["access_token"])
        
        media_source = {
            "source_type": "image_url",
            "url": str(request.image_url)
        }
        
        pin = client.create_pin(
            board_id=request.board_id,
            media_source=media_source,
            title=request.title,
            description=request.description or "",
            link=str(request.link) if request.link else ""
        )
        
        # Обновляем статус поста
        update_post_status(
            post["id"],
            "published",
            pinterest_pin_id=pin.get("id")
        )
        
        return {
            "success": True,
            "post_id": post["id"],
            "pinterest_pin_id": pin.get("id"),
            "status": "published"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error publishing pin: {e}")
        if post:
            update_post_status(post["id"], "failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Schedule Post ====================

@app.post("/api/schedule-post")
def schedule_post(request: SchedulePostRequest):
    """
    Запланировать публикацию пина
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=404, detail="Pinterest not connected")
        
        # Создаем запланированный пост
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "image_url": str(request.image_url),
            "title": request.title,
            "description": request.description or "",
            "link": str(request.link) if request.link else None,
            "status": "scheduled",
            "scheduled_at": request.scheduled_at.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        post = create_post(post_data)
        
        return {
            "success": True,
            "post_id": post["id"],
            "status": "scheduled",
            "scheduled_at": request.scheduled_at.isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error scheduling post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Posts ====================

@app.get("/api/posts")
def get_posts(
    user_id: str = Query(...),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Получить посты пользователя
    """
    try:
        posts = get_user_posts(user_id, status, limit, offset)
        return posts
    except Exception as e:
        print(f"Error fetching posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Stats & Analytics ====================

@app.get("/api/stats")
def get_stats(user_id: str = Query(...)):
    """
    Получить статистику пользователя
    """
    try:
        stats = get_user_stats(user_id)
        return stats
    except Exception as e:
        print(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/{post_id}")
def get_analytics(post_id: str, days: int = 30):
    """
    Получить аналитику для поста
    """
    try:
        analytics = get_post_analytics(post_id, days)
        return analytics
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/summary")
def get_analytics_summary(user_id: str = Query(...), days: int = 30):
    """
    Получить сводную аналитику пользователя
    """
    try:
        summary = get_user_analytics_summary(user_id, days)
        return summary
    except Exception as e:
        print(f"Error fetching analytics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Cleanup Task ====================

@app.on_event("startup")
async def startup_event():
    """Очистка при старте"""
    cleanup_old_oauth_states()
    print("✅ Old OAuth states cleaned up")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)