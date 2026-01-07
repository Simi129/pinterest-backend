# app/oauth.py
import requests
import os
from urllib.parse import urlencode
from typing import Dict, Optional
import base64

PINTEREST_OAUTH_URL = "https://www.pinterest.com/oauth/"
PINTEREST_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"

def get_authorization_url(redirect_uri: str, state: str) -> str:
    """
    Генерирует URL для авторизации пользователя в Pinterest
    """
    params = {
        "client_id": os.getenv("PINTEREST_APP_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "boards:read,boards:write,pins:read,pins:write,user_accounts:read",
        "state": state
    }
    return f"{PINTEREST_OAUTH_URL}?{urlencode(params)}"

def exchange_code_for_token(code: str, redirect_uri: str) -> Dict:
    """
    Обменивает authorization code на access token
    """
    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")
    
    # Создаём Basic Auth заголовок
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
        response = requests.post(PINTEREST_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error exchanging code for token: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def refresh_access_token(refresh_token: str) -> Dict:
    """
    Обновляет access token используя refresh token
    """
    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")
    
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
        response = requests.post(PINTEREST_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing token: {e}")
        raise