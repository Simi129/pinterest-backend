from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime
import asyncio

from app.models import PublishNowRequest, SchedulePostRequest, PostResponse
from app.pinterest import get_pinterest_client
from app.database import create_post, update_post_status

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

# Функция публикации
async def publish_post(post_id: str):
    """Публикация поста в Pinterest"""
    try:
        # Получаем пост из БД
        from app.database import get_post
        post = get_post(post_id)
        
        if not post:
            print(f"Post {post_id} not found")
            return
        
        # Публикуем в Pinterest
        pinterest = get_pinterest_client()
        pin = pinterest.create_pin(
            board_id=post["board_id"],
            image_url=post["image_url"],
            title=post["title"],
            description=post["description"] or "",
            link=post.get("link", "")
        )
        
        # Обновляем статус
        update_post_status(post_id, "published", pin.get("id"))
        print(f"Post {post_id} published successfully")
        
    except Exception as e:
        print(f"Error publishing post {post_id}: {e}")
        update_post_status(post_id, "failed")

# Фоновая задача для отложенной публикации
async def schedule_publish(post_id: str, scheduled_at: datetime):
    """Ждёт до нужного времени и публикует"""
    now = datetime.utcnow()
    wait_seconds = (scheduled_at - now).total_seconds()
    
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
    
    await publish_post(post_id)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Pinterest Automation API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/publish-now")
async def publish_now(request: PublishNowRequest, background_tasks: BackgroundTasks):
    """Немедленная публикация"""
    try:
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
        background_tasks.add_task(publish_post, post["id"])
        
        return {"status": "publishing", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-post")
async def schedule_post_endpoint(request: SchedulePostRequest, background_tasks: BackgroundTasks):
    """Запланированная публикация"""
    try:
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
        background_tasks.add_task(schedule_publish, post["id"], request.scheduled_at)
        
        return {"status": "scheduled", "post_id": post["id"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))