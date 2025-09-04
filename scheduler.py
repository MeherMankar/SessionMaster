import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from database import db
from session_operations import send_message_to_user
from utils import sanitize_log_input

class MessageScheduler:
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the message scheduler"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logging.info("Message scheduler started")
    
    async def stop(self):
        """Stop the message scheduler"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logging.info("Message scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._process_pending_messages()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Scheduler error: {sanitize_log_input(str(e))}")
                await asyncio.sleep(60)
    
    async def _process_pending_messages(self):
        """Process pending scheduled messages"""
        try:
            pending_messages = db.get_pending_messages()
            
            for message_data in pending_messages:
                try:
                    success = await send_message_to_user(
                        message_data['session_path'],
                        message_data['recipient'],
                        message_data['message'],
                        message_data['media_path']
                    )
                    
                    status = 'sent' if success else 'failed'
                    db.update_message_status(message_data['id'], status)
                    
                    # Log the action
                    db.log_action(
                        message_data['user_id'],
                        'scheduled_message_sent' if success else 'scheduled_message_failed',
                        {
                            'recipient': message_data['recipient'],
                            'message_id': message_data['id']
                        },
                        message_data['session_id']
                    )
                    
                except Exception as e:
                    logging.error(f"Failed to send scheduled message {message_data['id']}: {e}")
                    db.update_message_status(message_data['id'], 'failed')
                
                # Small delay between messages
                await asyncio.sleep(2)
                
        except Exception as e:
            logging.error(f"Error processing pending messages: {sanitize_log_input(str(e))}")

class AutoReplyManager:
    def __init__(self):
        self.active_sessions = {}
    
    async def start_auto_reply(self, user_id: int, session_path: str):
        """Start auto-reply for a session"""
        if user_id in self.active_sessions:
            return
        
        task = asyncio.create_task(self._auto_reply_loop(user_id, session_path))
        self.active_sessions[user_id] = task
        logging.info(f"Auto-reply started for user {sanitize_log_input(str(user_id))}")
    
    async def stop_auto_reply(self, user_id: int):
        """Stop auto-reply for a session"""
        if user_id in self.active_sessions:
            task = self.active_sessions.pop(user_id)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logging.info(f"Auto-reply stopped for user {sanitize_log_input(str(user_id))}")
    
    async def _auto_reply_loop(self, user_id: int, session_path: str):
        """Auto-reply loop for a specific session"""
        # This would implement real-time message monitoring and auto-reply
        # For now, it's a placeholder that could be extended with Telethon's event handlers
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                # Implementation would go here
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Auto-reply error for user {user_id}: {e}")
                await asyncio.sleep(60)

# Global instances
message_scheduler = MessageScheduler()
auto_reply_manager = AutoReplyManager()