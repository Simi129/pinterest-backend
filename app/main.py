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
    delete_pinterest_connection,
    save_oauth_state, get_oauth_state, cleanup_old_oauth_states
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

# Функция публикации
async def publish_post(post_id: str, user_id: str):
    """Публикация поста в Pinterest"""
    try:
        post = get_post(post_id)
        
        if not post:
            print(f"Post {post_id} not found")
            return
        
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            print(f"No Pinterest connection for user {user_id}")
            update_post_status(post_id, "failed")
            return
        
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
        
        update_post_status(post_id, "published", pin.get("id"))
        print(f"Post {post_id} published successfully. Pin ID: {pin.get('id')}")
        
    except Exception as e:
        print(f"Error publishing post {post_id}: {e}")
        update_post_status(post_id, "failed")

async def schedule_publish(post_id: str, user_id: str, scheduled_at: datetime):
    """Ждёт до нужного времени и публикует"""
    now = datetime.utcnow()
    wait_seconds = (scheduled_at - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"Waiting {wait_seconds} seconds before publishing post {post_id}")
        await asyncio.sleep(wait_seconds)
    
    await publish_post(post_id, user_id)

@app.on_event("startup")
async def startup_event():
    """Очистка старых OAuth states при запуске"""
    cleanup_old_oauth_states()

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
    # Очищаем старые states
    cleanup_old_oauth_states()
    
    # Генерируем случайный state
    state = secrets.token_urlsafe(32)
    
    # Сохраняем state в БД
    if not save_oauth_state(state, user_id):
        raise HTTPException(status_code=500, detail="Failed to save OAuth state")
    
    # Формируем redirect_uri
    backend_url = os.getenv('BACKEND_URL', str(request.base_url).rstrip('/'))
    redirect_uri = f"{backend_url}/auth/pinterest/callback"
    
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
        # Получаем user_id из БД
        user_id = get_oauth_state(state)
        
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
        
        # Обмениваем code на access token
        backend_url = os.getenv('BACKEND_URL', str(request.base_url).rstrip('/'))
        redirect_uri = f"{backend_url}/auth/pinterest/callback"
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
    """Отключить Pinterest аккаунт"""
    try:
        delete_pinterest_connection(user_id)
        return {"status": "success", "message": "Pinterest disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/status")
def pinterest_status(user_id: str = Query(...)):
    """Проверить статус подключения Pinterest"""
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
    """Получить список досок пользователя"""
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
        
        background_tasks.add_task(publish_post, post["id"], request.user_id)
        
        return {"status": "publishing", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post")
async def schedule_post_endpoint(request: SchedulePostRequest, background_tasks: BackgroundTasks):
    """Запланированная публикация"""
    try:
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
        
        background_tasks.add_task(schedule_publish, post["id"], request.user_id, request.scheduled_at)
        
        return {"status": "scheduled", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))