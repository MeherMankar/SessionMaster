import os
import json
from typing import Dict, Any
from pathlib import Path

class Config:
    def __init__(self):
        self.config_file = Path("config.json")
        self.env_file = Path(".env")
        self._load_env_file()
        self._config = self._load_config()
    
    def _load_env_file(self):
        """Load environment variables from .env file"""
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    
    def _load_config(self) -> Dict[str, Any]:
        api_id = os.getenv("API_ID")
        config = {
            "api_id": int(api_id) if api_id else None,
            "api_hash": os.getenv("API_HASH"),
            "bot_token": os.getenv("BOT_TOKEN"),
            "database_path": "database.db",
            "sessions_dir": "sessions",
            "temp_dir": "temp",
            "tdata_dir": "TData",
            "max_sessions": 10,
            "rate_limit": 30,
            "log_level": "INFO",
            "encryption_key": os.getenv("ENCRYPTION_KEY"),
            "webhook_url": os.getenv("WEBHOOK_URL"),
            "proxy_url": os.getenv("PROXY_URL")
        }
        
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        
        return config
    
    def get(self, key: str, default=None):
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        self._config[key] = value
        self._save_config()
    
    def _save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)

config = Config()