# app/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
from datetime import datetime, timedelta
import asyncio
import secrets

from app.models import (
    PublishNowRequest, 
    SchedulePostRequest,
    CreateBoardRequest,
    UpdateBoardRequest
)
from app.pinterest import get_pinterest_client
from app.database import (
    create_post, update_post_status, get_post,
    create_pinterest_connection, get_pinterest_connection,
    delete_pinterest_connection,
    save_oauth_state, get_oauth_state, cleanup_old_oauth_states
)
from app.oauth import get_authorization_url, exchange_code_for_token

app = FastAPI(title="Pinterest Automation API", version="1.0.0")

# CORS Configuration
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

# ==================== Background Tasks ====================

async def publish_post(post_id: str, user_id: str):
    """Публикация поста в Pinterest"""
    try:
        post = get_post(post_id)
        
        if not post:
            print(f"❌ Post {post_id} not found")
            return
        
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            print(f"❌ No Pinterest connection for user {user_id}")
            update_post_status(post_id, "failed", error_message="Pinterest not connected")
            return
        
        pinterest = get_pinterest_client(connection["access_token"])
        
        # Определяем media_source в зависимости от типа изображения
        if post.get("image_base64"):
            media_source = {
                "source_type": "image_base64",
                "data": post["image_base64"]
            }
            print(f"📸 Creating pin with base64 image (size: {len(post['image_base64'])} chars)")
        elif post.get("image_url"):
            media_source = {
                "source_type": "image_url",
                "url": post["image_url"]
            }
            print(f"📸 Creating pin with image URL: {post['image_url']}")
        else:
            print(f"❌ No image provided for post {post_id}")
            update_post_status(post_id, "failed", error_message="No image provided")
            return
        
        pin = pinterest.create_pin(
            board_id=post["board_id"],
            media_source=media_source,
            title=post["title"],
            description=post.get("description", ""),
            link=post.get("link", "")
        )
        
        update_post_status(post_id, "published", pin.get("id"))
        print(f"✅ Post {post_id} published successfully. Pin ID: {pin.get('id')}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error publishing post {post_id}: {error_msg}")
        update_post_status(post_id, "failed", error_message=error_msg)

async def schedule_publish(post_id: str, user_id: str, scheduled_at: datetime):
    """Ждёт до нужного времени и публикует"""
    try:
        now = datetime.utcnow()
        wait_seconds = (scheduled_at - now).total_seconds()
        
        if wait_seconds > 0:
            print(f"⏰ Waiting {wait_seconds} seconds before publishing post {post_id}")
            await asyncio.sleep(wait_seconds)
        
        await publish_post(post_id, user_id)
    except Exception as e:
        print(f"❌ Error in schedule_publish for post {post_id}: {e}")

# ==================== Startup Event ====================

@app.on_event("startup")
async def startup_event():
    """Очистка старых OAuth states при запуске"""
    try:
        deleted_count = cleanup_old_oauth_states()
        print(f"🧹 Cleaned up {deleted_count} old OAuth states")
    except Exception as e:
        print(f"⚠️ Error cleaning up OAuth states: {e}")

# ==================== Health Check Endpoints ====================

@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "status": "ok",
        "message": "Pinterest Automation API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "auth": "/auth/pinterest",
            "boards": "/api/boards",
            "publish": "/api/publish-now",
            "schedule": "/api/schedule-post"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

# ==================== OAuth Endpoints ====================

@app.get("/auth/pinterest")
def pinterest_auth(request: Request, user_id: str = Query(...)):
    """Начало OAuth flow - редирект на Pinterest для авторизации"""
    try:
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
        
        print(f"🔐 Starting OAuth flow for user {user_id}")
        
        return RedirectResponse(auth_url)
    except Exception as e:
        print(f"❌ Error in pinterest_auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/callback")
async def pinterest_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...)
):
    """Callback после авторизации в Pinterest"""
    try:
        # Получаем user_id из БД
        user_id = get_oauth_state(state)
        
        if not user_id:
            print(f"❌ Invalid or expired state: {state}")
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
        
        print(f"✅ Pinterest connected successfully for user {user_id}")
        
        # Редирект обратно на фронтенд
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(f"{frontend_url}?pinterest_connected=true")
        
    except Exception as e:
        print(f"❌ Error in Pinterest callback: {e}")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        return RedirectResponse(f"{frontend_url}?pinterest_error=true")

@app.delete("/auth/pinterest/disconnect")
def disconnect_pinterest(user_id: str = Query(...)):
    """Отключить Pinterest аккаунт"""
    try:
        delete_pinterest_connection(user_id)
        print(f"🔌 Pinterest disconnected for user {user_id}")
        return {"status": "success", "message": "Pinterest disconnected"}
    except Exception as e:
        print(f"❌ Error disconnecting Pinterest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/status")
def pinterest_status(user_id: str = Query(...)):
    """Проверить статус подключения Pinterest"""
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            return {"connected": False}
        
        return {
            "connected": True,
            "pinterest_username": connection.get("pinterest_username"),
            "pinterest_user_id": connection.get("pinterest_user_id"),
            "connected_at": connection.get("created_at")
        }
    except Exception as e:
        print(f"❌ Error checking Pinterest status: {e}")
        return {"connected": False}

# ==================== Board Management Endpoints ====================

@app.get("/api/boards")
def get_boards(user_id: str = Query(...)):
    """Получить список досок пользователя"""
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        pinterest = get_pinterest_client(connection["access_token"])
        boards = pinterest.get_boards()
        
        print(f"📋 Retrieved {len(boards)} boards for user {user_id}")
        
        return {"boards": boards}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/boards/create")
def create_board(request: CreateBoardRequest):
    """Создать новую доску в Pinterest"""
    try:
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        pinterest = get_pinterest_client(connection["access_token"])
        board = pinterest.create_board(
            name=request.name,
            description=request.description,
            privacy=request.privacy
        )
        
        print(f"✅ Board created: {request.name} for user {request.user_id}")
        
        return {"status": "success", "board": board}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/boards/{board_id}")
def update_board(board_id: str, request: UpdateBoardRequest):
    """Обновить доску"""
    try:
        connection = get_pinterest_connection(request.user_id)
        
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        pinterest = get_pinterest_client(connection["access_token"])
        board = pinterest.update_board(
            board_id=board_id,
            name=request.name,
            description=request.description,
            privacy=request.privacy
        )
        
        print(f"✅ Board updated: {board_id} for user {request.user_id}")
        
        return {"status": "success", "board": board}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/boards/{board_id}")
def delete_board(board_id: str, user_id: str = Query(...)):
    """Удалить доску"""
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        pinterest = get_pinterest_client(connection["access_token"])
        pinterest.delete_board(board_id)
        
        print(f"🗑️ Board deleted: {board_id} for user {user_id}")
        
        return {"status": "success", "message": "Board deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Pin Management Endpoints ====================

@app.post("/api/publish-now")
async def publish_now_endpoint(request: PublishNowRequest, background_tasks: BackgroundTasks):
    """Немедленная публикация пина"""
    try:
        # Проверяем подключение
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        # Валидация: должен быть либо URL либо base64
        if not request.image_url and not request.image_base64:
            raise HTTPException(status_code=400, detail="Either image_url or image_base64 must be provided")
        
        # Подготовка данных для поста
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "title": request.title,
            "description": request.description,
            "link": str(request.link) if request.link else None,
            "status": "publishing"
        }
        
        # Добавляем изображение
        if request.image_base64:
            post_data["image_base64"] = request.image_base64
            print(f"📸 Publishing with base64 image")
        elif request.image_url:
            post_data["image_url"] = str(request.image_url)
            print(f"📸 Publishing with image URL: {request.image_url}")
        
        # Создаём пост в БД
        post = create_post(post_data)
        
        # Добавляем в фоновые задачи
        background_tasks.add_task(publish_post, post["id"], request.user_id)
        
        print(f"✅ Post {post['id']} queued for publishing")
        
        return {"status": "publishing", "post_id": post["id"]}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in publish_now: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post")
async def schedule_post_endpoint(request: SchedulePostRequest, background_tasks: BackgroundTasks):
    """Запланированная публикация пина"""
    try:
        # Проверяем подключение
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        # Валидация: должен быть либо URL либо base64
        if not request.image_url and not request.image_base64:
            raise HTTPException(status_code=400, detail="Either image_url or image_base64 must be provided")
        
        # Валидация времени
        if request.scheduled_at <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")
        
        # Подготовка данных для поста
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "title": request.title,
            "description": request.description,
            "link": str(request.link) if request.link else None,
            "scheduled_at": request.scheduled_at.isoformat(),
            "status": "scheduled"
        }
        
        # Добавляем изображение
        if request.image_base64:
            post_data["image_base64"] = request.image_base64
            print(f"📸 Scheduling with base64 image")
        elif request.image_url:
            post_data["image_url"] = str(request.image_url)
            print(f"📸 Scheduling with image URL: {request.image_url}")
        
        # Создаём пост в БД
        post = create_post(post_data)
        
        # Добавляем отложенную задачу
        background_tasks.add_task(schedule_publish, post["id"], request.user_id, request.scheduled_at)
        
        print(f"📅 Post {post['id']} scheduled for {request.scheduled_at}")
        
        return {"status": "scheduled", "post_id": post["id"]}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in schedule_post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Error Handlers ====================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return {
        "status": "error",
        "message": "Endpoint not found",
        "path": str(request.url)
    }

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 handler"""
    return {
        "status": "error",
        "message": "Internal server error",
        "detail": str(exc)
    }