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
    
    # ==================== User Info ====================
    
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
    
    # ==================== Boards ====================
    
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
    
    def create_board(
        self,
        name: str,
        description: str = "",
        privacy: str = "PUBLIC"
    ) -> Dict:
        """
        Создать новую доску в Pinterest
        
        Args:
            name: Название доски
            description: Описание доски (опционально)
            privacy: PUBLIC или SECRET (по умолчанию PUBLIC)
            
        Returns:
            Данные созданной доски
        """
        url = f"{self.base_url}/boards"
        
        # Нормализуем privacy значение
        privacy = privacy.upper()
        if privacy not in ["PUBLIC", "SECRET"]:
            print(f"⚠️ Invalid privacy value: {privacy}, defaulting to PUBLIC")
            privacy = "PUBLIC"
        
        # Формируем payload строго по документации Pinterest API v5
        payload = {
            "name": name.strip(),
            "privacy": privacy
        }
        
        # Добавляем description только если оно не пустое
        if description and description.strip():
            payload["description"] = description.strip()
        
        print(f"📤 Creating board with payload: {payload}")
        print(f"🔑 Using access token: {self.access_token[:20] if self.access_token else 'None'}...")
        print(f"🌐 Request URL: {url}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            print(f"📥 Response status: {response.status_code}")
            print(f"📥 Response headers: {dict(response.headers)}")
            
            if response.status_code != 201 and response.status_code != 200:
                print(f"❌ Non-success status code: {response.status_code}")
                print(f"❌ Response body: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            print(f"✅ Board created successfully")
            print(f"✅ Board data: {result}")
            return result
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error creating board: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response headers: {dict(e.response.headers)}")
                print(f"Response body: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error creating board: {e}")
            raise
        except Exception as e:
            print(f"❌ Unexpected error creating board: {e}")
            raise
    
    def update_board(
        self,
        board_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        privacy: Optional[str] = None
    ) -> Dict:
        """
        Обновить доску
        """
        url = f"{self.base_url}/boards/{board_id}"
        
        payload = {}
        if name:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if privacy:
            payload["privacy"] = privacy.upper()
        
        try:
            response = requests.patch(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error updating board: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def delete_board(self, board_id: str) -> bool:
        """
        Удалить доску
        """
        url = f"{self.base_url}/boards/{board_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error deleting board: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    # ==================== Pins ====================
    
    def create_pin(
        self,
        board_id: str,
        media_source: Dict,
        title: str,
        description: str = "",
        link: str = "",
        alt_text: str = "",
        keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Создание нового пина с поддержкой ключевых слов
        
        Args:
            board_id: ID доски Pinterest
            media_source: Источник медиа (image_url или image_base64)
            title: Заголовок пина
            description: Описание пина
            link: Ссылка для пина
            alt_text: Альтернативный текст для изображения
            keywords: Список ключевых слов для пина
            
        Returns:
            Данные созданного пина
        """
        url = f"{self.base_url}/pins"
        
        # Если переданы ключевые слова, добавляем их в description как хэштеги
        final_description = description
        if keywords and len(keywords) > 0:
            hashtags = " ".join([f"#{kw.strip().replace(' ', '')}" for kw in keywords])
            final_description = f"{description}\n\n{hashtags}".strip()
        
        payload = {
            "board_id": board_id,
            "title": title,
            "media_source": media_source
        }
        
        if final_description:
            payload["description"] = final_description
        if link:
            payload["link"] = link
        if alt_text:
            payload["alt_text"] = alt_text
        
        try:
            print(f"📌 Creating pin with title: {title}")
            if keywords:
                print(f"🏷️ Keywords: {', '.join(keywords)}")
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            print(f"✅ Pin created successfully: {result.get('id')}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating pin: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    def get_pins(self, page_size: int = 25, bookmark: Optional[str] = None) -> Dict:
        """
        Получить список пинов пользователя
        
        Args:
            page_size: Количество пинов на страницу (макс. 100)
            bookmark: Токен для пагинации (из предыдущего ответа)
            
        Returns:
            {"items": [...], "bookmark": "..."}
            Каждый пин содержит: id, title, description, link,
            created_at, media (images), board_id
        """
        url = f"{self.base_url}/pins"
        params = {"page_size": min(page_size, 100)}
        if bookmark:
            params["bookmark"] = bookmark
        
        try:
            print(f"📌 Fetching pins (page_size={page_size})")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Fetched {len(data.get('items', []))} pins")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching pins: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            raise

    def get_board_pins(self, board_id: str, page_size: int = 25, bookmark: Optional[str] = None) -> Dict:
        """
        Получить пины конкретной доски
        
        Args:
            board_id: ID доски
            page_size: Количество пинов на страницу (макс. 100)
            bookmark: Токен для пагинации
            
        Returns:
            {"items": [...], "bookmark": "..."}
        """
        url = f"{self.base_url}/boards/{board_id}/pins"
        params = {"page_size": min(page_size, 100)}
        if bookmark:
            params["bookmark"] = bookmark
        
        try:
            print(f"📌 Fetching pins for board {board_id} (page_size={page_size})")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Fetched {len(data.get('items', []))} pins for board {board_id}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching board pins: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
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
    
    # ==================== Analytics ====================
    
    def get_user_analytics(
        self,
        start_date: str,
        end_date: str,
        metric_types: str = "IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
    ) -> Dict:
        """
        Получить аналитику аккаунта пользователя
        
        Args:
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
            metric_types: Типы метрик через запятую
            
        Returns:
            Данные аналитики в формате {all: [...], daily_metrics: [...]}
        """
        url = f"{self.base_url}/user_account/analytics"
        
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": metric_types
        }
        
        try:
            print(f"📊 Fetching user analytics: {start_date} to {end_date}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Pinterest API возвращает структуру: {"all": {"daily_metrics": [...]}}
            # Преобразуем в формат, ожидаемый фронтендом: {"all": [...]}
            if "all" in data and isinstance(data["all"], dict):
                daily_metrics = data["all"].get("daily_metrics", [])
                print(f"✅ Analytics fetched successfully, converted {len(daily_metrics)} daily metrics")
                return {
                    "all": daily_metrics,
                    "daily_metrics": daily_metrics
                }
            
            print(f"✅ Analytics fetched successfully")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching user analytics: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def get_pin_analytics(
        self,
        pin_id: str,
        start_date: str,
        end_date: str,
        metric_types: str = "IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
    ) -> Dict:
        """
        Получить аналитику конкретного пина
        
        Args:
            pin_id: ID пина
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
            metric_types: Типы метрик через запятую
            
        Returns:
            Данные аналитики пина
        """
        url = f"{self.base_url}/pins/{pin_id}/analytics"
        
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": metric_types
        }
        
        try:
            print(f"📊 Fetching pin analytics for {pin_id}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "all" in data and isinstance(data["all"], dict):
                daily_metrics = data["all"].get("daily_metrics", [])
                print(f"✅ Pin analytics fetched successfully, converted {len(daily_metrics)} daily metrics")
                return {
                    "all": daily_metrics,
                    "daily_metrics": daily_metrics
                }
            
            print(f"✅ Pin analytics fetched successfully")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching pin analytics: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def get_board_analytics(
        self,
        board_id: str,
        start_date: str,
        end_date: str,
        metric_types: str = "IMPRESSION,OUTBOUND_CLICK,PIN_CLICK,SAVE"
    ) -> Dict:
        """
        Получить аналитику доски
        
        Args:
            board_id: ID доски
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
            metric_types: Типы метрик через запятую
            
        Returns:
            Данные аналитики доски
        """
        url = f"{self.base_url}/boards/{board_id}/analytics"
        
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": metric_types
        }
        
        try:
            print(f"📊 Fetching board analytics for {board_id}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "all" in data and isinstance(data["all"], dict):
                daily_metrics = data["all"].get("daily_metrics", [])
                print(f"✅ Board analytics fetched successfully, converted {len(daily_metrics)} daily metrics")
                return {
                    "all": daily_metrics,
                    "daily_metrics": daily_metrics
                }
            
            print(f"✅ Board analytics fetched successfully")
            return data
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching board analytics: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise


def get_pinterest_client(access_token: Optional[str] = None) -> PinterestClient:
    """
    Создать экземпляр Pinterest клиента
    """
    return PinterestClient(access_token)