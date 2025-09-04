import re
import os
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from telethon import TelegramClient
from config import config

def sanitize_log_input(text: str) -> str:
    """Sanitize input for logging to prevent log injection"""
    if not text:
        return ""
    return re.sub(r'[\r\n\t]', ' ', str(text)[:200])

def validate_path(path: str, base_dir: str) -> bool:
    """Validate file path to prevent directory traversal"""
    try:
        resolved_path = Path(path).resolve()
        base_path = Path(base_dir).resolve()
        return str(resolved_path).startswith(str(base_path))
    except:
        return False

def secure_filename(filename: str) -> str:
    """Generate secure filename"""
    filename = re.sub(r'[^\w\-_\.]', '', filename)
    return filename[:100] if filename else "file"

def hash_session_id(user_id: int) -> str:
    """Generate secure session identifier"""
    return hashlib.sha256(f"{user_id}_{config.get('encryption_key', 'default')}".encode()).hexdigest()[:16]

@asynccontextmanager
async def get_telegram_client(session_path: str):
    """Context manager for Telegram client with proper resource cleanup"""
    client = None
    try:
        client = TelegramClient(
            session_path,
            config.get('api_id'),
            config.get('api_hash'),
            device_model="Samsung SM-G973F",
            system_version="Android 10",
            app_version="8.4.1",
            lang_code="en",
            system_lang_code="en",
            proxy=config.get('proxy_url')
        )
        await client.connect()
        yield client
    finally:
        if client:
            await client.disconnect()

class RateLimiter:
    def __init__(self, max_calls: int = 30, time_window: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = {}
    
    def is_allowed(self, user_id: int) -> bool:
        import time
        now = time.time()
        if user_id not in self.calls:
            self.calls[user_id] = []
        
        self.calls[user_id] = [call for call in self.calls[user_id] if now - call < self.time_window]
        
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        
        self.calls[user_id].append(now)
        return True

rate_limiter = RateLimiter()

def format_session_info(info: Dict[str, Any]) -> str:
    """Format session information for display"""
    return f"""🆔 {info.get('name', 'Unknown')}
👤 Premium: {'Yes' if info.get('premium') else 'No'}
🔑 ID: {info.get('id', 'N/A')}
📛 Username: @{info.get('username', 'None')}
📞 Phone: {info.get('phone', 'Hidden')}
📬 Dialogs: {info.get('dialogs', 0)}
📇 Contacts: {info.get('contacts', 0)}
📢 Channels: {info.get('channels', 0)}
🤖 Bots: {info.get('bots', 0)}
💬 Groups: {info.get('groups', 0)}"""