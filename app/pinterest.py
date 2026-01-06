# app/pinterest.py
import requests
import os
from typing import Optional, Dict

class PinterestClient:
    """
    Клиент для работы с Pinterest API
    """
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("PINTEREST_ACCESS_TOKEN")
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def create_pin(
        self,
        board_id: str,
        image_url: str,
        title: str,
        description: str = "",
        link: str = ""
    ) -> Dict:
        """
        Создание нового пина в Pinterest
        
        Args:
            board_id: ID доски Pinterest
            image_url: URL изображения
            title: Заголовок пина
            description: Описание пина
            link: Ссылка для пина
            
        Returns:
            Данные созданного пина
        """
        url = f"{self.base_url}/pins"
        
        payload = {
            "board_id": board_id,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            },
            "title": title,
            "description": description,
        }
        
        if link:
            payload["link"] = link
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating pin: {e}")
            raise
    
    def get_boards(self) -> Dict:
        """
        Получить список досок пользователя
        """
        url = f"{self.base_url}/boards"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching boards: {e}")
            raise
    
    def get_pin(self, pin_id: str) -> Dict:
        """
        Получить информацию о пине
        """
        url = f"{self.base_url}/pins/{pin_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching pin: {e}")
            raise
    
    def get_pin_analytics(self, pin_id: str) -> Dict:
        """
        Получить аналитику по пину
        """
        url = f"{self.base_url}/pins/{pin_id}/analytics"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching analytics: {e}")
            raise


# Вспомогательная функция для быстрого создания клиента
def get_pinterest_client(access_token: Optional[str] = None) -> PinterestClient:
    """
    Создать экземпляр Pinterest клиента
    """
    return PinterestClient(access_token)