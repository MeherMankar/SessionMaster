import logging
import asyncio
import io
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import User, Channel, Chat, InputPhoneContact
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from config import config
from exceptions import *
from utils import sanitize_log_input, get_telegram_client
from database import db

async def validate_session(session_path: str) -> bool:
    """Validate a Telegram session file"""
    try:
        async with get_telegram_client(session_path) as client:
            me = await client.get_me()
            logging.info(f"Session validated for user ID: {sanitize_log_input(str(me.id))}")
            return True
    except Exception as e:
        logging.error(f"Session validation failed: {sanitize_log_input(str(e))}")
        return False

async def get_session_info(session_path: str) -> Dict[str, Any]:
    """Get comprehensive session information"""
    try:
        async with get_telegram_client(session_path) as client:
            me = await client.get_me()
            dialogs = await client.get_dialogs()
            
            # Count different types of entities
            stats = {"contacts": 0, "channels": 0, "bots": 0, "groups": 0, "private_chats": 0}
            
            for dialog in dialogs:
                entity = dialog.entity
                if isinstance(entity, User):
                    if getattr(entity, "bot", False):
                        stats["bots"] += 1
                    else:
                        stats["private_chats"] += 1
                elif isinstance(entity, Channel):
                    if getattr(entity, "broadcast", False):
                        stats["channels"] += 1
                    else:
                        stats["groups"] += 1
                elif isinstance(entity, Chat):
                    stats["groups"] += 1
            
            # Get avatar
            avatar = None
            try:
                if me.photo:
                    avatar_bytes = await client.download_profile_photo(me, file=bytes)
                    if avatar_bytes:
                        avatar = io.BytesIO(avatar_bytes)
                        avatar.name = "avatar.jpg"
            except Exception:
                pass  # Avatar download failed, continue without it
            
            info = {
                "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
                "premium": getattr(me, "premium", False),
                "verified": getattr(me, "verified", False),
                "id": me.id,
                "username": me.username,
                "phone": me.phone,
                "dialogs": len(dialogs),
                "avatar": avatar,
                **stats
            }
            
            logging.info(f"Session info retrieved for user {sanitize_log_input(str(me.id))}")
            return info
            
    except Exception as e:
        logging.error(f"Error getting session info: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to get session info: {e}")

async def subscribe_to_channel(session_path, channel_link):
    try:
        async with get_telegram_client(session_path) as client:
            await client(JoinChannelRequest(channel_link))
            logging.debug(f"Subscribed to {channel_link}")
            return True
    except Exception as e:
        logging.error(f"Error subscribing to {channel_link}: {e}")
        return False

async def check_spam_block(session_path):
    try:
        async with get_telegram_client(session_path) as client:
            test_bot = await client.get_entity("spambot")
            await client.send_message(test_bot, "/start")
            messages = await client.get_messages(test_bot, limit=1)
            if messages and messages[0].message:
                result = "ограничен" in messages[0].message.lower()
                logging.debug(f"Spam check: {'Blocked' if result else 'Not blocked'}")
                return result
            return False
    except Exception as e:
        logging.error(f"Spam check error: {e}")
        return False

async def send_message_to_user(session_path, recipient, text=None, media_path=None):
    try:
        async with get_telegram_client(session_path) as client:
            if media_path:
                await client.send_file(recipient, media_path, caption=text)
            else:
                await client.send_message(recipient, text)
        logging.debug(f"Message sent to {recipient}")
        return True
    except Exception as e:
        logging.error(f"Error sending message to {recipient}: {e}")
        return False

async def delete_dialogs_by_type(session_path, dialog_type):
    try:
        async with get_telegram_client(session_path) as client:
            count = await _delete_dialogs(client, dialog_type)
        logging.debug(f"Deleted {count} dialogs of type {dialog_type}")
        return True
    except Exception as e:
        logging.error(f"Error deleting dialogs of type {dialog_type}: {e}")
        return False

async def _delete_dialogs(client, dialog_type):
    dialogs = await client.get_dialogs()
    count = 0
    for dialog in dialogs:
        entity = dialog.entity
        if dialog_type == "channels":
            if isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                await client.delete_dialog(entity)
                count += 1
        elif dialog_type == "chats":
            if isinstance(entity, (Channel, Chat)) and not getattr(entity, "broadcast", False):
                await client.delete_dialog(entity)
                count += 1
        elif dialog_type == "bots":
            if isinstance(entity, User) and getattr(entity, "bot", False):
                await client.delete_dialog(entity)
                count += 1
        elif dialog_type == "personal":
            if isinstance(entity, User) and not getattr(entity, "bot", False):
                await client.delete_dialog(entity)
                count += 1
    return count

async def export_contacts(session_path):
    try:
        async with get_telegram_client(session_path) as client:
            contacts_result = await client(GetContactsRequest(hash=0))
            users = contacts_result.users
            text_lines = []
            for user in users:
                name = user.first_name or ""
                if user.last_name:
                    name += " " + user.last_name
                username = user.username if user.username else ""
                phone = user.phone if user.phone else ""
                text_lines.append(f"{name}\t{username}\t{phone}")
            contacts_text = "\n".join(text_lines)
            if not contacts_text.strip():
                contacts_text = "Нет контактов"
            file_obj = io.BytesIO(contacts_text.encode("utf-8"))
            file_obj.name = "contacts.txt"
            return file_obj
    except Exception as e:
        logging.error(f"Error exporting contacts: {e}")
        return None

async def check_crypto_wallet(session_path):
    try:
        async with get_telegram_client(session_path) as client:
            target = "send"
            await client.send_message(target, "/wallet")
            await asyncio.sleep(3)
            messages = await client.get_messages(target, limit=1)
            if messages and messages[0].message:
                text = messages[0].message
                lines = text.splitlines()
                result_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("👛"):
                        continue
                    if ":" in line:
                        try:
                            parts = line.split(":", 1)
                            amount_part = parts[1].strip()
                            tokens = amount_part.split()
                            if tokens:
                                amount_str = tokens[0].replace(",", ".")
                                try:
                                    amount = float(amount_str)
                                except:
                                    amount = 0.0
                                if amount != 0.0:
                                    result_lines.append(line)
                        except Exception:
                            continue
                if not result_lines:
                    return "Баланс пуст"
                else:
                    return "\n".join(result_lines)
            else:
                return "Не удалось получить ответ от @send"
    except Exception as e:
        logging.error(f"Error in check_crypto_wallet: {e}")
        return "Ошибка проверки криптовалют"