# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

from app.models import PublishNowRequest, SchedulePostRequest, PostResponse
from app.pinterest import get_pinterest_client
from app.database import create_post, update_post_status
from app.tasks import publish_to_pinterest

app = FastAPI(title="Pinterest Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://autopin-five.vercel.app/",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Pinterest Automation API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/publish-now", response_model=PostResponse)
async def publish_now(request: PublishNowRequest):
    """
    Немедленная публикация в Pinterest
    """
    try:
        # Создаём запись в БД
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
        
        # Публикуем в Pinterest
        pinterest = get_pinterest_client()
        pin = pinterest.create_pin(
            board_id=request.board_id,
            image_url=str(request.image_url),
            title=request.title,
            description=request.description,
            link=str(request.link) if request.link else ""
        )
        
        # Обновляем статус
        update_post_status(post["id"], "published", pin.get("id"))
        
        return PostResponse(**post, status="published", pinterest_pin_id=pin.get("id"))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post", response_model=PostResponse)
async def schedule_post(request: SchedulePostRequest):
    """
    Запланировать публикацию
    """
    try:
        # Создаём запись в БД
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
        
        # Добавляем задачу в Celery
        publish_to_pinterest.apply_async(
            args=[post["id"]], 
            eta=request.scheduled_at
        )
        
        return PostResponse(**post)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
