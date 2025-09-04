#!/usr/bin/env python3
"""
SessionMaster - Advanced Telegram Session Management Bot
Main application file
"""

import telebot
import asyncio
import os
import logging
import io
import sys
import time
import shutil
import threading
from datetime import datetime
from pathlib import Path
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Import modules with error handling
try:
    from config import config
    from database import db
    from utils import sanitize_log_input, get_telegram_client
    from session_manager import (
        validate_session, get_session_info, subscribe_to_channel,
        check_spam_block, send_message_to_user, delete_dialogs_by_type,
        export_contacts, check_crypto_wallet
    )
    from session_operations import create_tdata
    from exceptions import ConfigurationError
    from strings import STRINGS
    from scheduler import message_scheduler
    from async_worker import AsyncWorker
    from auth_manager import auth_manager
    from web_interface import start_web
except ImportError as e:
    print(f"Import warning: {e}")
    # Create minimal fallbacks
    STRINGS = {'bot_started': 'Bot started successfully'}

# Ensure auth_manager imported separately so phone auth still works if other optional imports fail
AUTH_AVAILABLE = False
try:
    from auth_manager import auth_manager
    AUTH_AVAILABLE = True
except Exception as e:
    logging.warning(f"Auth manager not available: {e}")

# Global variables
bot = None
TOKEN = None
pending_message = {}
async_worker = None

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )

def create_directories():
    """Create necessary directories"""
    directories = ['sessions', 'temp', 'logs', 'tdata']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def check_config():
    """Check configuration"""
    required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN']
    missing = []
    
    for var in required_vars:
        if not config.get(var.lower()):
            missing.append(var)
    
    if missing:
        print(f"Missing configuration: {', '.join(missing)}")
        return False
    return True

def get_user_session(user_id):
    """Get user session path"""
    session_path = f"sessions/id_{user_id}.session"
    if os.path.exists(session_path):
        return session_path
    return None

def run_coro_sync(coro):
    """Run coroutine synchronously"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        logging.error(f"Error running coroutine: {e}")
        return None
    finally:
        loop.close()

def send_session_info(message, session_id, info):
    """Send session information to user"""
    if not info:
        bot.send_message(message.chat.id, "Error getting session information.")
        return
    
    text = f"📱 **Session Info**\\n\\n"
    text += f"👤 **Name:** {info.get('name', 'Unknown')}\\n"
    text += f"🆔 **ID:** {info.get('id', 'Unknown')}\\n"
    text += f"📞 **Phone:** {info.get('phone', 'Unknown')}\\n"
    
    if info.get('username'):
        text += f"📛 **Username:** @{info['username']}\\n"
    
    text += f"💬 **Dialogs:** {info.get('dialogs', 0)}\\n"
    text += f"📢 **Channels:** {info.get('channels', 0)}\\n"
    text += f"👥 **Groups:** {info.get('groups', 0)}\\n"
    text += f"🤖 **Bots:** {info.get('bots', 0)}\\n"
    text += f"💭 **Private Chats:** {info.get('private_chats', 0)}\\n"
    
    if info.get('premium'):
        text += "⭐ **Premium Account**\\n"
    if info.get('verified'):
        text += "✅ **Verified Account**\\n"
    
    # Create inline keyboard
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📊 Update", callback_data="update"),
        InlineKeyboardButton("🚫 Spam Check", callback_data="spamcheck")
    )
    markup.row(
        InlineKeyboardButton("💬 Send Message", callback_data="message_user"),
        InlineKeyboardButton("📢 Subscribe", callback_data="subscribe")
    )
    markup.row(
        InlineKeyboardButton("🗑️ Delete Dialogs", callback_data="delete"),
        InlineKeyboardButton("📋 Export Contacts", callback_data="import_contacts")
    )
    markup.row(
        InlineKeyboardButton("💾 Generate TData", callback_data="tdata"),
        InlineKeyboardButton("💰 Check Wallet", callback_data="toggle_crypto")
    )
    
    try:
        if info.get('avatar'):
            bot.send_photo(message.chat.id, info['avatar'], caption=text, 
                          reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error sending session info: {e}")
        # Fallback without markdown
        bot.send_message(message.chat.id, text.replace('*', ''), reply_markup=markup)

def register_handlers():
    """Register bot handlers"""
    
    @bot.message_handler(commands=["start"])
    def start_handler(message):
        session_path = get_user_session(message.chat.id)
        if session_path:
            try:
                info = run_coro_sync(get_session_info(session_path))
                session_id = f"id_{message.chat.id}"
                send_session_info(message, session_id, info)
            except Exception as e:
                logging.error(f"Error getting session info: {e}")
                bot.send_message(message.chat.id, "Error getting session information.")
        else:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📱 Add by Phone", callback_data="add_session_phone"))
            bot.send_message(message.chat.id, "No sessions found. Choose how to add your account:", reply_markup=markup)
            bot.send_message(message.chat.id, "Or send a .session file directly")

    @bot.message_handler(content_types=['document'])
    def handle_session_file(message):
        if not message.document.file_name.endswith(".session"):
            bot.reply_to(message, "Please send a .session file")
            return
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
        except Exception as e:
            logging.error(f"Error downloading file: {e}")
            bot.reply_to(message, "Error downloading file.")
            return
        session_path = f"sessions/id_{message.chat.id}.session"
        try:
            with open(session_path, "wb") as f:
                f.write(downloaded_file)
            logging.debug(f"Session file saved to {session_path}")
        except Exception as e:
            logging.error(f"Error saving session file: {e}")
            bot.reply_to(message, "Error saving file.")
            return

        if run_coro_sync(validate_session(session_path)):
            try:
                if 'db' in globals():
                    db.save_session(message.chat.id, f"id_{message.chat.id}", session_path)
                info = run_coro_sync(get_session_info(session_path))
                session_id = f"id_{message.chat.id}"
                send_session_info(message, session_id, info)
            except Exception as e:
                logging.error(f"Error processing session info: {e}")
                bot.reply_to(message, "Error processing session information.")
        else:
            os.remove(session_path)
            logging.warning(f"Session file {session_path} is invalid.")
            bot.reply_to(message, "Invalid session file.")

    @bot.callback_query_handler(func=lambda call: call.data == "subscribe")
    def handle_subscribe(call):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logging.error(f"Error deleting message: {e}")
        msg = bot.send_message(call.message.chat.id, "Send channel link:")
        bot.register_next_step_handler(msg, process_subscription)

    def process_subscription(message):
        session_path = get_user_session(message.chat.id)
        if not session_path:
            bot.send_message(message.chat.id, "Session not found, please send session file.")
            return

        if run_coro_sync(subscribe_to_channel(session_path, message.text)):
            bot.send_message(message.chat.id, "Successfully subscribed!")
            try:
                info = run_coro_sync(get_session_info(session_path))
                session_id = f"id_{message.chat.id}"
                send_session_info(message, session_id, info)
            except Exception as e:
                logging.error(f"Error refreshing session info after subscription: {e}")
                bot.send_message(message.chat.id, "Error updating session information.")
        else:
            bot.send_message(message.chat.id, "Subscription error.")

    @bot.callback_query_handler(func=lambda call: call.data == "spamcheck")
    def handle_spam_check(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        result = run_coro_sync(check_spam_block(session_path))
        bot.answer_callback_query(call.id, f"Spam block: {'Yes' if result else 'No'}")

    @bot.callback_query_handler(func=lambda call: call.data == "update")
    def handle_update(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        try:
            info = run_coro_sync(get_session_info(session_path))
            session_id = f"id_{call.message.chat.id}"
            bot.send_message(call.message.chat.id, "Updated data:")
            send_session_info(call.message, session_id, info)
        except Exception as e:
            logging.error(f"Error updating session info: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "message_user")
    def handle_message_user(call):
        bot.send_message(call.message.chat.id, "Enter recipient username (without @):")
        bot.register_next_step_handler(call.message, process_recipient_username)

    def process_recipient_username(message):
        chat_id = message.chat.id
        pending_message[chat_id] = {"recipient": message.text.strip()}
        bot.send_message(chat_id, "Enter message text or send photo/video/file:")
        bot.register_next_step_handler(message, process_message_content)

    def process_message_content(message):
        chat_id = message.chat.id
        if chat_id not in pending_message or "recipient" not in pending_message[chat_id]:
            bot.send_message(chat_id, "Error: recipient not specified.")
            return
        recipient = pending_message[chat_id]["recipient"]
        session_path = get_user_session(chat_id)
        if not session_path:
            bot.send_message(chat_id, "Session not found.")
            return
        text = None
        media_path = None
        if message.content_type == "text":
            text = message.text
        elif message.content_type in ["photo", "video", "document"]:
            try:
                if message.content_type == "photo":
                    file_info = bot.get_file(message.photo[-1].file_id)
                elif message.content_type == "video":
                    file_info = bot.get_file(message.video.file_id)
                elif message.content_type == "document":
                    file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                if not os.path.exists("temp"):
                    os.makedirs("temp")
                if message.content_type == "document":
                    filename = message.document.file_name
                elif message.content_type == "photo":
                    filename = f"{message.message_id}_photo.jpg"
                elif message.content_type == "video":
                    filename = f"{message.message_id}_video.mp4"
                media_path = os.path.join("temp", filename)
                with open(media_path, "wb") as f:
                    f.write(downloaded_file)
            except Exception as e:
                logging.error(f"Error downloading media: {e}")
                bot.send_message(chat_id, "Error downloading file.")
                return
        else:
            bot.send_message(chat_id, "Unsupported message type.")
            return

        result = run_coro_sync(send_message_to_user(session_path, recipient, text, media_path))
        if result:
            bot.send_message(chat_id, "Message sent.")
        else:
            bot.send_message(chat_id, "Message sending error.")
        if media_path and os.path.exists(media_path):
            os.remove(media_path)
        pending_message.pop(chat_id, None)

    @bot.callback_query_handler(func=lambda call: call.data == "delete")
    def handle_delete(call):
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("All Channels", callback_data="delete_channels"),
            InlineKeyboardButton("All Chats", callback_data="delete_chats")
        )
        markup.row(
            InlineKeyboardButton("All Bots", callback_data="delete_bots"),
            InlineKeyboardButton("All Private Dialogs", callback_data="delete_personal")
        )
        bot.send_message(call.message.chat.id, "What to delete?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
    def handle_delete_type(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        dialog_type = call.data.replace("delete_", "")
        result = delete_dialogs_by_type(session_path, dialog_type)
        if result:
            bot.answer_callback_query(call.id, f"Deleted {dialog_type}.")
        else:
            bot.answer_callback_query(call.id, "Deletion error.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logging.error(f"Error deleting delete selection message: {e}")
        try:
            info = run_coro_sync(get_session_info(session_path))
            session_id = f"id_{call.message.chat.id}"
            bot.send_message(call.message.chat.id, "Updated data:")
            send_session_info(call.message, session_id, info)
        except Exception as e:
            logging.error(f"Error updating session info after deletion: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "import_contacts")
    def handle_import_contacts(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        contacts_file = run_coro_sync(export_contacts(session_path))
        if contacts_file:
            contacts_file.seek(0)
            bot.send_document(call.message.chat.id, contacts_file, caption="Contacts")
            bot.answer_callback_query(call.id, "Contacts exported.")
        else:
            bot.answer_callback_query(call.id, "Contact export error.")

    @bot.callback_query_handler(func=lambda call: call.data == "tdata")
    def handle_tdata(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        try:
            zip_path = run_coro_sync(create_tdata(session_path))
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    bot.send_document(call.message.chat.id, f, caption="TData archive")
                bot.answer_callback_query(call.id, "TData generated.")
                os.remove(zip_path)
                dir_path = os.path.dirname(zip_path)
                shutil.rmtree(dir_path, ignore_errors=True)
            else:
                bot.answer_callback_query(call.id, "TData generation error.")
        except Exception as e:
            logging.error(f"TData generation error: {e}")
            bot.answer_callback_query(call.id, "TData generation error.")

    @bot.callback_query_handler(func=lambda call: call.data == "toggle_crypto")
    def handle_crypto(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        result = run_coro_sync(check_crypto_wallet(session_path))
        bot.send_message(call.message.chat.id, f"💵 Your balance:\\n\\n{result}")
        bot.answer_callback_query(call.id, "Check completed.")

    @bot.message_handler(commands=["wallet"])
    def wallet_handler(message):
        session_path = get_user_session(message.chat.id)
        if not session_path:
            bot.send_message(message.chat.id, "Session not found!")
            return
        result = run_coro_sync(check_crypto_wallet(session_path))
        bot.send_message(message.chat.id, f"💵 Your balance:\\n\\n{result}")

    # Phone authentication handlers
    @bot.callback_query_handler(func=lambda call: call.data == "add_session_phone")
    def handle_add_phone(call):
        """Handle add account by phone"""
        bot.send_message(call.message.chat.id, "Enter your phone number (with country code, e.g., +1234567890):")
        bot.register_next_step_handler(call.message, process_phone_number)
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data == "resend_code")
    def handle_resend_code(call):
        """Handle resend code button"""
        try:
            if AUTH_AVAILABLE:
                result = auth_manager.resend_code(call.message.chat.id)
                if result['success']:
                    bot.send_message(call.message.chat.id, f"📨 {result['message']}")
                    bot.send_message(call.message.chat.id, "⏳ Please wait a few seconds, then enter the new verification code:")
                    bot.register_next_step_handler(call.message, process_verification_code)
                else:
                    bot.send_message(call.message.chat.id, f"❌ {result['error']}")
            try:
                bot.answer_callback_query(call.id)
            except:
                pass
        except Exception as e:
            logging.error(f"Resend callback error: {e}")
            try:
                bot.answer_callback_query(call.id, "Error resending code")
            except:
                pass
    
    @bot.callback_query_handler(func=lambda call: call.data == "restart_auth")
    def handle_restart_auth(call):
        """Handle restart auth button"""
        try:
            if AUTH_AVAILABLE:
                auth_manager.cancel_auth(call.message.chat.id)
            bot.send_message(call.message.chat.id, "Authentication cancelled. Enter your phone number to start again:")
            bot.register_next_step_handler(call.message, process_phone_number)
            try:
                bot.answer_callback_query(call.id)
            except:
                pass
        except Exception as e:
            logging.error(f"Restart auth error: {e}")
            try:
                bot.answer_callback_query(call.id, "Error restarting auth")
            except:
                pass

    def process_phone_number(message):
        """Process phone number input"""
        phone = str(message.text).strip()
        
        # Basic phone validation
        if not phone.startswith('+') or len(phone) < 10:
            bot.send_message(message.chat.id, "Invalid phone format. Please use format: +1234567890")
            return
        
        # Start authentication
        try:
            if AUTH_AVAILABLE:
                result = auth_manager.start_phone_auth(message.chat.id, phone)
                if result['success']:
                    bot.send_message(message.chat.id, result['message'])
                    bot.send_message(message.chat.id, "⏳ Please wait a few seconds, then enter the verification code:")
                    bot.register_next_step_handler(message, process_verification_code)
                else:
                    error_msg = result['error']
                    if 'api_id/api_hash combination is invalid' in error_msg:
                        bot.send_message(message.chat.id, "❌ Invalid API credentials. Please contact the bot administrator to update API_ID and API_HASH from https://my.telegram.org/apps")
                    else:
                        bot.send_message(message.chat.id, f"Error: {error_msg}")
            else:
                bot.send_message(message.chat.id, "Phone authentication not available. Please upload a .session file instead.")
        except Exception as e:
            logging.error(f"Phone auth error: {e}")
            bot.send_message(message.chat.id, f"Error: {str(e)}")

    def process_verification_code(message):
        """Process verification code input"""
        code = message.text.strip()
        
        try:
            if AUTH_AVAILABLE:
                result = auth_manager.verify_code(message.chat.id, code)

                if result['success']:
                    if result['step'] == 'complete':
                        # Authentication complete
                        user_info = result['user_info']
                        text = f"✅ Successfully logged in!\\n\\n👤 {user_info['name']}\\n🆔 {user_info['id']}\\n📱 {user_info['phone']}"
                        if user_info['username']:
                            text += f"\\n📛 @{user_info['username']}"

                        bot.send_message(message.chat.id, text)

                    elif result['step'] == '2fa':
                        # Need 2FA password
                        bot.send_message(message.chat.id, result['message'])
                        bot.register_next_step_handler(message, process_2fa_password)
                else:
                    error_msg = result['error']
                    bot.send_message(message.chat.id, f"❌ {error_msg}")
                    
                    if result.get('expired'):
                        # Code expired, offer resend option
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("📨 Resend Code", callback_data="resend_code"))
                        markup.add(InlineKeyboardButton("🔄 Restart Auth", callback_data="restart_auth"))
                        bot.send_message(message.chat.id, "🔄 Code expired. Choose an option:", reply_markup=markup)
                    else:
                        # Allow retry
                        bot.send_message(message.chat.id, "Please enter the verification code again:")
                        bot.register_next_step_handler(message, process_verification_code)
            else:
                bot.send_message(message.chat.id, "Authentication not available.")
        except Exception as e:
            logging.error(f"Verification error: {e}")
            bot.send_message(message.chat.id, f"Error: {str(e)}")

    def process_2fa_password(message):
        """Process 2FA password input"""
        password = message.text.strip()
        
        # Delete the password message for security
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        try:
            if AUTH_AVAILABLE:
                result = auth_manager.verify_2fa(message.chat.id, password)

                if result['success']:
                    # Authentication complete
                    user_info = result['user_info']
                    text = f"✅ Successfully logged in with 2FA!\\n\\n👤 {user_info['name']}\\n🆔 {user_info['id']}\\n📱 {user_info['phone']}"
                    if user_info['username']:
                        text += f"\\n📛 @{user_info['username']}"

                    bot.send_message(message.chat.id, text)
                else:
                    bot.send_message(message.chat.id, f"❌ {result['error']}")
                    # Allow retry
                    bot.send_message(message.chat.id, "Please enter your 2FA password again:")
                    bot.register_next_step_handler(message, process_2fa_password)
            else:
                bot.send_message(message.chat.id, "2FA authentication not available.")
        except Exception as e:
            logging.error(f"2FA error: {e}")
            bot.send_message(message.chat.id, f"Error: {str(e)}")

    @bot.message_handler(commands=['cancel'])
    def cancel_handler(message):
        """Cancel any pending authentication"""
        try:
            if AUTH_AVAILABLE and auth_manager.cancel_auth(message.chat.id):
                bot.send_message(message.chat.id, "❌ Authentication cancelled.")
            else:
                bot.send_message(message.chat.id, "No pending authentication to cancel.")
        except Exception as e:
            logging.error(f"Cancel error: {e}")
            bot.send_message(message.chat.id, "Error cancelling authentication.")

    @bot.message_handler(commands=['addphone'])
    def addphone_handler(message):
        """Quick command to add phone"""
        bot.send_message(message.chat.id, "Enter your phone number (with country code, e.g., +1234567890):")
        bot.register_next_step_handler(message, process_phone_number)
    
    @bot.message_handler(commands=['resend'])
    def resend_handler(message):
        """Resend verification code"""
        try:
            if AUTH_AVAILABLE:
                result = auth_manager.resend_code(message.chat.id)
                if result['success']:
                    bot.send_message(message.chat.id, f"📨 {result['message']}")
                    bot.send_message(message.chat.id, "⏳ Please wait a few seconds, then enter the new verification code:")
                    bot.register_next_step_handler(message, process_verification_code)
                else:
                    bot.send_message(message.chat.id, f"❌ {result['error']}")
            else:
                bot.send_message(message.chat.id, "Resend not available.")
        except Exception as e:
            logging.error(f"Resend error: {e}")
            bot.send_message(message.chat.id, f"Error: {str(e)}")

def initialize_bot():
    """Initialize the bot instance"""
    global TOKEN, bot, async_worker
    TOKEN = config.get('bot_token')
    if not TOKEN:
        raise ConfigurationError("Bot token not configured")
    
    # Validate API credentials early
    api_id = config.get('api_id')
    api_hash = config.get('api_hash')
    if not api_id or not str(api_id).isdigit():
        raise ConfigurationError("API_ID missing or invalid. Please set API_ID in your .env")
    if not api_hash or len(str(api_hash)) != 32:
        raise ConfigurationError("API_HASH missing or invalid. Get credentials from https://my.telegram.org/apps")

    # Start async worker if available
    try:
        if 'AsyncWorker' in globals():
            async_worker = AsyncWorker()
            async_worker.start()
    except Exception as e:
        logging.warning(f"Could not start async worker: {e}")

    bot = telebot.TeleBot(TOKEN)
    register_handlers()
    logging.info(STRINGS.get('bot_started', 'Bot started successfully'))

def start_scheduler():
    """Start the message scheduler"""
    try:
        if 'message_scheduler' in globals():
            def _start_scheduler():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(message_scheduler.start())
                loop.run_forever()
            
            scheduler_thread = threading.Thread(target=_start_scheduler, daemon=True)
            scheduler_thread.start()
    except Exception as e:
        logging.warning(f"Could not start scheduler: {e}")

def start_bot():
    """Start the Telegram bot"""
    try:
        print("Starting Telegram bot...")
        start_scheduler()
        
        while True:
            try:
                bot.polling(none_stop=True, timeout=60)
            except Exception as e:
                logging.error(f"Polling error: {sanitize_log_input(str(e)) if 'sanitize_log_input' in globals() else str(e)}")
                time.sleep(15)
    except Exception as e:
        logging.error(f"Bot error: {e}")
        time.sleep(5)
        start_bot()  # Restart on error

def main():
    """Main launcher function"""
    print("SessionMaster v2.0")
    print("=" * 50)
    
    # Setup
    setup_logging()
    
    if not check_config():
        sys.exit(1)
    
    create_directories()
    initialize_bot()
    
    print("Configuration validated")
    print("Directories created")
    
    # Start services
    try:
        # Start web interface in background thread if available
        try:
            if 'start_web' in globals():
                web_thread = threading.Thread(target=start_web, daemon=True)
                web_thread.start()
                print("Web interface started on http://localhost:5000")
        except Exception as e:
            logging.warning(f"Could not start web interface: {e}")
        
        # Start bot in main thread
        start_bot()
        
    except KeyboardInterrupt:
        print("\\nShutting down SessionMaster...")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()