# app/pinterest.py
import requests
import os
from typing import Optional, Dict, List

class PinterestClient:
    """
    Клиент для работы с Pinterest API v5
    """
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("PINTEREST_ACCESS_TOKEN")
        self.base_url = "https://api.pinterest.com/v5"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def get_user_info(self) -> Dict:
        """
        Получить информацию о текущем пользователе
        """
        url = f"{self.base_url}/user_account"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting user info: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def get_boards(self) -> List[Dict]:
        """
        Получить список досок пользователя
        """
        url = f"{self.base_url}/boards"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching boards: {e}")
            raise
    
    def create_pin(
        self,
        board_id: str,
        media_source: Dict,
        title: str,
        description: str = "",
        link: str = "",
        alt_text: str = ""
    ) -> Dict:
        """
        Создание нового пина
        
        Args:
            board_id: ID доски Pinterest
            media_source: Источник медиа (image_url или image_base64)
            title: Заголовок пина
            description: Описание пина
            link: Ссылка для пина
            alt_text: Альтернативный текст для изображения
            
        Returns:
            Данные созданного пина
        """
        url = f"{self.base_url}/pins"
        
        payload = {
            "board_id": board_id,
            "title": title,
            "media_source": media_source
        }
        
        if description:
            payload["description"] = description
        
        if link:
            payload["link"] = link
            
        if alt_text:
            payload["alt_text"] = alt_text
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating pin: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
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
    
    def delete_pin(self, pin_id: str) -> bool:
        """
        Удалить пин
        """
        url = f"{self.base_url}/pins/{pin_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error deleting pin: {e}")
            raise


def get_pinterest_client(access_token: Optional[str] = None) -> PinterestClient:
    """
    Создать экземпляр Pinterest клиента
    """
    return PinterestClient(access_token)