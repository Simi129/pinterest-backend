# app/tasks.py
from celery import Celery
import os

celery = Celery(
    'tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

@celery.task
def publish_to_pinterest(post_id):
    # Достаёшь пост из Supabase
    # Публикуешь в Pinterest
    # Обновляешь статус в базе
    pass