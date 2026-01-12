# app/main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.models import (
    PublishNowRequest, 
    SchedulePostRequest,
    CreateBoardRequest,
    UpdateBoardRequest
)
from app.pinterest import get_pinterest_client
from app.oauth import get_authorization_url, exchange_code_for_token, refresh_access_token
from app.database import (
    get_pinterest_connection,
    create_pinterest_connection,
    delete_pinterest_connection,
    create_post,
    get_scheduled_posts
)
import os
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI(title="Pinterest Scheduler API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://autopin-five.vercel.app",
        "https://pinflow.org"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIRECT_URI = os.getenv("PINTEREST_REDIRECT_URI", "https://pinterest-backend-1b8a.onrender.com/auth/pinterest/callback")

# ==================== OAuth Routes ====================

@app.get("/auth/pinterest")
async def pinterest_auth(user_id: str):
    """
    Инициирует OAuth процесс для Pinterest
    """
    try:
        auth_url = get_authorization_url(
            redirect_uri=REDIRECT_URI,
            state=user_id
        )
        return RedirectResponse(url=auth_url)
    except Exception as e:
        print(f"Error initiating Pinterest OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/pinterest/callback")
async def pinterest_callback(code: str, state: str):
    """
    Callback для Pinterest OAuth
    """
    try:
        user_id = state
        
        # Обмениваем code на token
        token_data = exchange_code_for_token(code, REDIRECT_URI)
        
        # Получаем информацию о пользователе Pinterest
        client = get_pinterest_client(token_data["access_token"])
        user_info = client.get_user_info()
        
        # Рассчитываем expires_at
        expires_in = token_data.get("expires_in", 0)
        expires_at = None
        if expires_in:
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        
        # Сохраняем токен в БД используя create_pinterest_connection
        connection_data = {
            "user_id": user_id,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "pinterest_user_id": user_info.get("username"),
            "pinterest_username": user_info.get("username"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        create_pinterest_connection(connection_data)
        
        return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/dashboard/settings?pinterest_connected=true")
        
    except Exception as e:
        print(f"Error in Pinterest callback: {e}")
        return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/dashboard/settings?pinterest_error={str(e)}")

@app.get("/auth/pinterest/status")
async def get_pinterest_status(user_id: str):
    """
    Проверяет статус подключения Pinterest
    """
    try:
        connection = get_pinterest_connection(user_id)
        
        if not connection:
            return {"connected": False}
        
        return {
            "connected": True,
            "pinterest_username": connection.get("pinterest_username"),
            "pinterest_user_id": connection.get("pinterest_user_id")
        }
    except Exception as e:
        print(f"Error checking Pinterest status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/auth/pinterest/disconnect")
async def disconnect_pinterest(user_id: str):
    """
    Отключает Pinterest аккаунт
    """
    try:
        delete_pinterest_connection(user_id)
        return {"success": True, "message": "Pinterest disconnected successfully"}
    except Exception as e:
        print(f"Error disconnecting Pinterest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Board Routes ====================

@app.get("/api/boards")
async def get_boards(user_id: str):
    """
    Получить список досок пользователя
    """
    try:
        connection = get_pinterest_connection(user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        boards = client.get_boards()
        
        return {"boards": boards}
    except Exception as e:
        print(f"Error fetching boards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/boards/create")
async def create_board(request: CreateBoardRequest):
    """
    Создать новую доску
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        board = client.create_board(
            name=request.name,
            description=request.description or "",
            privacy=request.privacy or "PUBLIC"
        )
        
        return {"success": True, "board": board}
    except Exception as e:
        print(f"Error creating board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/boards/{board_id}")
async def update_board(board_id: str, request: UpdateBoardRequest):
    """
    Обновить доску
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        board = client.update_board(
            board_id=board_id,
            name=request.name,
            description=request.description,
            privacy=request.privacy
        )
        
        return {"success": True, "board": board}
    except Exception as e:
        print(f"Error updating board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/boards/{board_id}")
async def delete_board(board_id: str, user_id: str):
    """
    Удалить доску
    """
    try:
        connection = get_pinterest_connection(user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        client.delete_board(board_id)
        
        return {"success": True, "message": "Board deleted successfully"}
    except Exception as e:
        print(f"Error deleting board: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Pin Routes ====================

@app.post("/api/publish-now")
async def publish_now(request: PublishNowRequest):
    """
    Немедленная публикация пина
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        
        # Создаем пин с поддержкой keywords
        pin = client.create_pin(
            board_id=request.board_id,
            media_source={
                "source_type": "image_url",
                "url": str(request.image_url)
            },
            title=request.title,
            description=request.description or "",
            link=str(request.link) if request.link else "",
            keywords=request.keywords if hasattr(request, 'keywords') else None
        )
        
        return {
            "success": True,
            "pin_id": pin.get("id"),
            "pin": pin
        }
    except Exception as e:
        print(f"Error publishing pin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post")
async def schedule_post(request: SchedulePostRequest):
    """
    Запланировать публикацию пина
    """
    try:
        connection = get_pinterest_connection(request.user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        # Сохраняем запланированный пост в БД
        post_data = {
            "user_id": request.user_id,
            "board_id": request.board_id,
            "image_url": str(request.image_url),
            "title": request.title,
            "description": request.description or "",
            "link": str(request.link) if request.link else "",
            "scheduled_at": request.scheduled_at.isoformat(),
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat()
        }
        
        post = create_post(post_data)
        
        return {
            "success": True,
            "post_id": post["id"] if post else None,
            "scheduled_at": request.scheduled_at
        }
    except Exception as e:
        print(f"Error scheduling post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Analytics Routes ====================

@app.get("/api/analytics/account")
async def get_account_analytics(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """
    Получить аналитику аккаунта
    """
    try:
        connection = get_pinterest_connection(user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        
        # Рассчитываем даты
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        analytics = client.get_user_analytics(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            metric_types="IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
        )
        
        return {
            "success": True,
            "analytics": analytics,
            "period": {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "days": days
            }
        }
    except Exception as e:
        print(f"Error fetching account analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/pin/{pin_id}")
async def get_pin_analytics(
    pin_id: str,
    user_id: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """
    Получить аналитику конкретного пина
    """
    try:
        connection = get_pinterest_connection(user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        
        # Рассчитываем даты
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        analytics = client.get_pin_analytics(
            pin_id=pin_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            metric_types="IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
        )
        
        return {
            "success": True,
            "analytics": analytics,
            "pin_id": pin_id
        }
    except Exception as e:
        print(f"Error fetching pin analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/board/{board_id}")
async def get_board_analytics(
    board_id: str,
    user_id: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """
    Получить аналитику доски
    """
    try:
        connection = get_pinterest_connection(user_id)
        if not connection:
            raise HTTPException(status_code=401, detail="Pinterest not connected")
        
        client = get_pinterest_client(connection["access_token"])
        
        # Рассчитываем даты
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        analytics = client.get_board_analytics(
            board_id=board_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            metric_types="IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
        )
        
        return {
            "success": True,
            "analytics": analytics,
            "board_id": board_id
        }
    except Exception as e:
        print(f"Error fetching board analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Health Check ====================

@app.get("/")
async def root():
    return {"message": "Pinterest Scheduler API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}