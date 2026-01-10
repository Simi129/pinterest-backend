# app/oauth.py
import requests
import os
import secrets
from urllib.parse import urlencode
from typing import Dict, Tuple
import base64

PINTEREST_OAUTH_URL = "https://www.pinterest.com/oauth/"
PINTEREST_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"

def get_pinterest_auth_url() -> Tuple[str, str]:
    """
    Генерирует URL для авторизации пользователя в Pinterest
    
    Returns:
        Tuple[str, str]: (auth_url, state)
    """
    # Генерируем state для CSRF защиты
    state = secrets.token_urlsafe(32)
    
    redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "http://localhost:8000/auth/pinterest/callback")
    
    params = {
        "client_id": os.getenv("PINTEREST_APP_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "ads:read,boards:read,boards:write,pins:read,pins:write,user_accounts:read",
        "state": state
    }
    
    auth_url = f"{PINTEREST_OAUTH_URL}?{urlencode(params)}"
    print(f"🔗 Generated OAuth URL with state: {state}")
    
    return auth_url, state

def get_authorization_url(redirect_uri: str, state: str) -> str:
    """
    Генерирует URL для авторизации пользователя в Pinterest
    (Оставлена для обратной совместимости)
    
    Args:
        redirect_uri: URL для возврата после авторизации
        state: CSRF токен для безопасности
        
    Returns:
        URL для редиректа пользователя на страницу авторизации Pinterest
    """
    params = {
        "client_id": os.getenv("PINTEREST_APP_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "ads:read,boards:read,boards:write,pins:read,pins:write,user_accounts:read",
        "state": state
    }
    
    auth_url = f"{PINTEREST_OAUTH_URL}?{urlencode(params)}"
    print(f"🔗 Generated OAuth URL with scopes: ads:read,boards:read,boards:write,pins:read,pins:write,user_accounts:read")
    
    return auth_url

def exchange_code_for_token(code: str, redirect_uri: str = None) -> Dict:
    """
    Обменивает authorization code на access token
    
    Args:
        code: Authorization code из callback
        redirect_uri: Опциональный redirect_uri (если не указан, берется из env)
        
    Returns:
        Dict с access_token, refresh_token, expires_in и другими данными
    """
    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")
    
    # Используем переданный redirect_uri или берём из переменной окружения
    if not redirect_uri:
        redirect_uri = os.getenv("PINTEREST_REDIRECT_URI", "http://localhost:8000/auth/pinterest/callback")
    
    if not app_id or not app_secret:
        raise ValueError("PINTEREST_APP_ID and PINTEREST_APP_SECRET must be set")
    
    # Создаём Basic Auth заголовок (требуется для Pinterest API v5)
    credentials = f"{app_id}:{app_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    try:
        print(f"🔄 Exchanging code for token...")
        response = requests.post(PINTEREST_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        print(f"✅ Token exchange successful. Expires in: {token_data.get('expires_in', 'unknown')} seconds")
        
        return token_data
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error exchanging code for token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error exchanging code for token: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error exchanging code for token: {e}")
        raise

def refresh_pinterest_token(refresh_token: str) -> Dict:
    """
    Обновляет access token используя refresh token
    (Alias для refresh_access_token)
    
    Args:
        refresh_token: Refresh token полученный при авторизации
        
    Returns:
        Dict с новым access_token и другими данными
    """
    return refresh_access_token(refresh_token)

def refresh_access_token(refresh_token: str) -> Dict:
    """
    Обновляет access token используя refresh token
    
    Args:
        refresh_token: Refresh token полученный при авторизации
        
    Returns:
        Dict с новым access_token и другими данными
    """
    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")
    
    if not app_id or not app_secret:
        raise ValueError("PINTEREST_APP_ID and PINTEREST_APP_SECRET must be set")
    
    # Создаём Basic Auth заголовок
    credentials = f"{app_id}:{app_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    try:
        print(f"🔄 Refreshing access token...")
        response = requests.post(PINTEREST_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        print(f"✅ Token refresh successful. Expires in: {token_data.get('expires_in', 'unknown')} seconds")
        
        return token_data
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error refreshing token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error refreshing token: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error refreshing token: {e}")
        raise

def validate_token(access_token: str) -> bool:
    """
    Проверяет валидность access token
    
    Args:
        access_token: Access token для проверки
        
    Returns:
        True если токен валиден, False если нет
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Проверяем токен запросом к user_account endpoint
        response = requests.get(
            "https://api.pinterest.com/v5/user_account",
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"✅ Token is valid")
            return True
        else:
            print(f"❌ Token is invalid. Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return False