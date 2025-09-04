"""
Database operations for SessionMaster
"""

import sqlite3
import logging
from typing import Optional

class Database:
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        session_name TEXT,
                        session_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logging.error(f"Database init error: {e}")
    
    def save_session(self, user_id: int, session_name: str, session_path: str) -> Optional[int]:
        """Save session to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO sessions (user_id, session_name, session_path) VALUES (?, ?, ?)",
                    (user_id, session_name, session_path)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Save session error: {e}")
            return None
    
    def get_user_sessions(self, user_id: int):
        """Get all sessions for a user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
                )
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Get sessions error: {e}")
            return []

# Global database instance
db = Database()