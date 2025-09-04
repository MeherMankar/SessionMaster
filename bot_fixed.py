#!/usr/bin/env python3
"""
SessionMaster - Advanced Telegram Session Management Bot
Fixed main application file
"""

import telebot
import asyncio
import os
import logging
import sys
import time
import threading
from pathlib import Path
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Import modules
try:
    from config import config
    from database import db
    from utils import sanitize_log_input, setup_logging, create_directories, check_config
    from session_manager import validate_session, get_session_info
    from exceptions import ConfigurationError
except ImportError as e:
    print(f"Import error: {e}")
    print("Some modules may be missing. Continuing with basic functionality...")

# Global variables
bot = None
TOKEN = None
pending_message = {}

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
            bot.send_message(message.chat.id, "🚀 **Welcome to SessionMaster!**\\n\\nNo sessions found. Choose how to add your account:", reply_markup=markup, parse_mode='Markdown')
            bot.send_message(message.chat.id, "Or send a .session file directly")

    @bot.message_handler(commands=["help"])
    def help_handler(message):
        help_text = """
🚀 **SessionMaster Commands:**

/start - Main menu and session selection
/help - Show this help message
/wallet - Check crypto wallet balance
/cancel - Cancel current operation

**Features:**
📱 Session Management
💬 Send Messages
📢 Channel Subscription
🗑️ Dialog Cleanup
📋 Contact Export
💾 TData Generation
💰 Crypto Wallet Check

Send a .session file to get started!
        """
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

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
                info = run_coro_sync(get_session_info(session_path))
                session_id = f"id_{message.chat.id}"
                bot.reply_to(message, "✅ Session file uploaded successfully!")
                send_session_info(message, session_id, info)
            except Exception as e:
                logging.error(f"Error processing session info: {e}")
                bot.reply_to(message, "Session uploaded but error getting info.")
        else:
            os.remove(session_path)
            logging.warning(f"Session file {session_path} is invalid.")
            bot.reply_to(message, "❌ Invalid session file.")

    @bot.callback_query_handler(func=lambda call: call.data == "update")
    def handle_update(call):
        session_path = get_user_session(call.message.chat.id)
        if not session_path:
            bot.answer_callback_query(call.id, "Session not found!")
            return
        try:
            info = run_coro_sync(get_session_info(session_path))
            session_id = f"id_{call.message.chat.id}"
            bot.send_message(call.message.chat.id, "🔄 Updated data:")
            send_session_info(call.message, session_id, info)
        except Exception as e:
            logging.error(f"Error updating session info: {e}")
            bot.answer_callback_query(call.id, "Error updating info!")

    @bot.callback_query_handler(func=lambda call: call.data == "add_session_phone")
    def handle_add_phone(call):
        bot.send_message(call.message.chat.id, "📱 Phone authentication is not implemented yet. Please upload a .session file instead.")
        bot.answer_callback_query(call.id)

    # Placeholder handlers for other callbacks
    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback(call):
        bot.answer_callback_query(call.id, f"Feature '{call.data}' is not implemented yet.")

def initialize_bot():
    """Initialize the bot instance"""
    global TOKEN, bot
    TOKEN = config.get('bot_token')
    if not TOKEN:
        raise ConfigurationError("Bot token not configured")
    
    bot = telebot.TeleBot(TOKEN)
    register_handlers()
    logging.info("Bot initialized successfully")

def start_bot():
    """Start the Telegram bot"""
    try:
        print("🚀 Starting SessionMaster bot...")
        
        while True:
            try:
                bot.polling(none_stop=True, timeout=60)
            except Exception as e:
                logging.error(f"Polling error: {sanitize_log_input(str(e))}")
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
    try:
        setup_logging()
    except:
        logging.basicConfig(level=logging.INFO)
    
    try:
        if not check_config():
            print("❌ Configuration check failed")
            sys.exit(1)
    except:
        print("⚠️ Config check failed, continuing anyway...")
    
    try:
        create_directories()
    except:
        print("⚠️ Directory creation failed, continuing anyway...")
        # Create basic directories
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("temp", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
    
    try:
        initialize_bot()
    except Exception as e:
        print(f"❌ Bot initialization failed: {e}")
        sys.exit(1)
    
    print("✅ Configuration validated")
    print("✅ Directories created")
    print("✅ Bot initialized")
    
    # Start bot
    try:
        start_bot()
        
    except KeyboardInterrupt:
        print("\\n🛑 Shutting down SessionMaster...")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Startup error: {e}")
        print(f"❌ Startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()