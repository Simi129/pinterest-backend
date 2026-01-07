# app/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
from datetime import datetime, timedelta
import asyncio
import secrets

from app.models import PublishNowRequest, SchedulePostRequest
from app.pinterest import get_pinterest_client
from app.database import (
    create_post, update_post_status, get_post,
    create_pinterest_connection, get_pinterest_connection,
    delete_pinterest_connection
)
from app.oauth import get_authorization_url, exchange_code_for_token

app = FastAPI(title="Pinterest Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://autopin-five.vercel.app",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Временное хранилище для state (в продакшене используй Redis или БД)
oauth_states = {}

# Функция публикации
async def publish_post(post_id: str, user_id: str):
    """Публикация поста в Pinterest"""
    try:
        # Получаем пост из БД
        post = get_post(post_id)
        
        if not post:
            print(f"Post {post_id} not found")
            return
        
        # Получаем токен пользователя
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            print(f"No Pinterest connection for user {user_id}")
            update_post_status(post_id, "failed")
            return
        
        # Публикуем в Pinterest
        pinterest = get_pinterest_client(connection["access_token"])
        
        media_source = {
            "source_type": "image_url",
            "url": post["image_url"]
        }
        
        pin = pinterest.create_pin(
            board_id=post["board_id"],
            media_source=media_source,
            title=post["title"],
            description=post.get("description", ""),
            link=post.get("link", "")
        )
        
        # Обновляем статус
        update_post_status(post_id, "published", pin.get("id"))
        print(f"Post {post_id} published successfully. Pin ID: {pin.get('id')}")
        
    except Exception as e:
        print(f"Error publishing post {post_id}: {e}")
        update_post_status(post_id, "failed")

# Фоновая задача для отложенной публикации
async def schedule_publish(post_id: str, user_id: str, scheduled_at: datetime):
    """Ждёт до нужного времени и публикует"""
    now = datetime.utcnow()
    wait_seconds = (scheduled_at - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"Waiting {wait_seconds} seconds before publishing post {post_id}")
        await asyncio.sleep(wait_seconds)
    
    await publish_post(post_id, user_id)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Pinterest Automation API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# ==================== OAuth Endpoints ====================

@app.get("/auth/pinterest")
def pinterest_auth(request: Request, user_id: str = Query(...)):
    """
    Начало OAuth flow - редирект на Pinterest для авторизации
    """
    # Генерируем случайный state для защиты от CSRF
    state = secrets.token_urlsafe(32)
    
    # Сохраняем state с user_id (в продакшене используй Redis)
    oauth_states[state] = {
        "user_id": user_id,
        "created_at": datetime.utcnow()
    }
    
    # Формируем redirect_uri из base URL
    base_url = str(request.base_url).rstrip('/')
    redirect_uri = f"{base_url}/auth/pinterest/callback"
    
    # Генерируем URL авторизации
    auth_url = get_authorization_url(redirect_uri, state)
    
    return RedirectResponse(auth_url)

@app.get("/auth/pinterest/callback")
async def pinterest_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    Callback после авторизации в Pinterest
    """
    try:
        # Проверяем state
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        state_data = oauth_states.pop(state)
        user_id = state_data["user_id"]
        
        # Обмениваем code на access token
        base_url = str(request.base_url).rstrip('/')
        redirect_uri = f"{base_url}/auth/pinterest/callback"
        token_data = exchange_code_for_token(code, redirect_uri)
        
        # Получаем информацию о пользователе Pinterest
        pinterest = get_pinterest_client(token_data["access_token"])
        pinterest_user = pinterest.get_user_info()
        
        # Сохраняем подключение в БД
        connection_data = {
            "user_id": user_id,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": (datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 0))).isoformat() if token_data.get("expires_in") else None,
            "pinterest_user_id": pinterest_user.get("id"),
            "pinterest_username": pinterest_user.get("username"),
            "scopes": token_data.get("scope", "").split(",")
        }
        
        create_pinterest_connection(connection_data)
        
        # Редирект обратно на фронтенд
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(f"{frontend_url}?pinterest_connected=true")
        
    except Exception as e:
        print(f"Error in Pinterest callback: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(f"{frontend_url}?pinterest_error=true")

@app.delete("/auth/pinterest/disconnect")
def disconnect_pinterest(user_id: str = Query(...)):
    """
    Отключить Pinterest аккаунт
    """
    try:
        delete_pinterest_connection(user_id)
        return {"status": "success", "message": "Pinterest disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/status")
def pinterest_status(user_id: str = Query(...)):
    """
    Проверить статус подключения Pinterest
    """
    connection = get_pinterest_connection(user_id)
    
    if not connection:
        return {"connected": False}
    
    return {
        "connected": True,
        "pinterest_username": connection.get("pinterest_username"),
        "pinterest_user_id": connection.get("pinterest_user_id"),
        "connected_at": connection.get("created_at")
    }

# ==================== Pinterest API Endpoints ====================

@app.get("/api/boards")
def get_boards(user_id: str = Query(...)):
    """
    Получить список досок пользователя
    """
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        pinterest = get_pinterest_client(connection["access_token"])
        boards = pinterest.get_boards()
        
        return {"boards": boards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/publish-now")
async def publish_now(request: PublishNowRequest, background_tasks: BackgroundTasks):
    """Немедленная публикация"""
    try:
        # Проверяем подключение
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "image_url": str(request.image_url),
            "title": request.title,
            "description": request.description,
            "link": str(request.link) if request.link else None,
            "status": "publishing"
        }
        post = create_post(post_data)
        
        # Добавляем в фоновые задачи
        background_tasks.add_task(publish_post, post["id"], request.user_id)
        
        return {"status": "publishing", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post")
async def schedule_post_endpoint(request: SchedulePostRequest, background_tasks: BackgroundTasks):
    """Запланированная публикация"""
    try:
        # Проверяем подключение
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "image_url": str(request.image_url),
            "title": request.title,
            "description": request.description,
            "link": str(request.link) if request.link else None,
            "scheduled_at": request.scheduled_at.isoformat(),
            "status": "scheduled"
        }
        post = create_post(post_data)
        
        # Добавляем отложенную задачу
        background_tasks.add_task(schedule_publish, post["id"], request.user_id, request.scheduled_at)
        
        return {"status": "scheduled", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))