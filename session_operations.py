import asyncio
import io
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest
from telethon.tl.functions.messages import GetHistoryRequest, SendMessageRequest
from telethon.tl.types import InputPhoneContact, User, Channel, Chat
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError
from utils import get_telegram_client, sanitize_log_input
from exceptions import TelegramAPIError
from database import db
import logging

async def subscribe_to_channel(session_path: str, channel_link: str) -> bool:
    """Subscribe to a channel or group"""
    try:
        async with get_telegram_client(session_path) as client:
            await client(JoinChannelRequest(channel_link))
            logging.info(f"Successfully subscribed to {sanitize_log_input(channel_link)}")
            return True
    except FloodWaitError as e:
        logging.warning(f"Rate limited for {e.seconds} seconds")
        raise TelegramAPIError(f"Rate limited. Wait {e.seconds} seconds")
    except Exception as e:
        logging.error(f"Error subscribing to channel: {sanitize_log_input(str(e))}")
        return False

async def unsubscribe_from_channel(session_path: str, channel_link: str) -> bool:
    """Unsubscribe from a channel or group"""
    try:
        async with get_telegram_client(session_path) as client:
            entity = await client.get_entity(channel_link)
            await client(LeaveChannelRequest(entity))
            logging.info(f"Successfully unsubscribed from {sanitize_log_input(channel_link)}")
            return True
    except Exception as e:
        logging.error(f"Error unsubscribing from channel: {sanitize_log_input(str(e))}")
        return False

async def bulk_subscribe(session_path: str, channel_links: List[str], delay: int = 5) -> Dict[str, bool]:
    """Subscribe to multiple channels with delay"""
    results = {}
    for channel_link in channel_links:
        try:
            result = await subscribe_to_channel(session_path, channel_link)
            results[channel_link] = result
            if delay > 0:
                await asyncio.sleep(delay)
        except Exception as e:
            results[channel_link] = False
            logging.error(f"Failed to subscribe to {sanitize_log_input(channel_link)}: {e}")
    return results

async def check_spam_block(session_path: str) -> bool:
    """Check if account is spam blocked"""
    try:
        async with get_telegram_client(session_path) as client:
            try:
                spambot = await client.get_entity("spambot")
                await client.send_message(spambot, "/start")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(spambot, limit=1)
                if messages and messages[0].message:
                    message_text = messages[0].message.lower()
                    is_blocked = any(word in message_text for word in ["ограничен", "limited", "restricted"])
                    logging.info(f"Spam check result: {'Blocked' if is_blocked else 'Not blocked'}")
                    return is_blocked
                return False
            except Exception:
                return False
    except Exception as e:
        logging.error(f"Spam check error: {sanitize_log_input(str(e))}")
        return False

async def send_message_to_user(session_path: str, recipient: str, text: str = None, 
                              media_path: str = None, parse_mode: str = None) -> bool:
    """Send message to user with optional media"""
    try:
        async with get_telegram_client(session_path) as client:
            entity = await client.get_entity(recipient)
            
            if media_path:
                await client.send_file(entity, media_path, caption=text, parse_mode=parse_mode)
            else:
                await client.send_message(entity, text, parse_mode=parse_mode)
            
            logging.info(f"Message sent to {sanitize_log_input(recipient)}")
            return True
    except UserPrivacyRestrictedError:
        logging.warning(f"User {sanitize_log_input(recipient)} has restricted privacy settings")
        return False
    except FloodWaitError as e:
        logging.warning(f"Rate limited for {e.seconds} seconds")
        raise TelegramAPIError(f"Rate limited. Wait {e.seconds} seconds")
    except Exception as e:
        logging.error(f"Error sending message: {sanitize_log_input(str(e))}")
        return False

async def bulk_send_messages(session_path: str, recipients: List[str], text: str, 
                           delay: int = 5, media_path: str = None) -> Dict[str, bool]:
    """Send messages to multiple recipients"""
    results = {}
    for recipient in recipients:
        try:
            result = await send_message_to_user(session_path, recipient, text, media_path)
            results[recipient] = result
            if delay > 0:
                await asyncio.sleep(delay)
        except Exception as e:
            results[recipient] = False
            logging.error(f"Failed to send message to {sanitize_log_input(recipient)}: {e}")
    return results

async def delete_dialogs_by_type(session_path: str, dialog_type: str) -> int:
    """Delete dialogs by type with improved performance"""
    try:
        async with get_telegram_client(session_path) as client:
            dialogs = await client.get_dialogs()
            
            # Collect entities to delete
            to_delete = []
            for dialog in dialogs:
                entity = dialog.entity
                should_delete = False
                
                if dialog_type == "channels" and isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "groups" and isinstance(entity, (Channel, Chat)) and not getattr(entity, "broadcast", False):
                    should_delete = True
                elif dialog_type == "bots" and isinstance(entity, User) and getattr(entity, "bot", False):
                    should_delete = True
                elif dialog_type == "private" and isinstance(entity, User) and not getattr(entity, "bot", False):
                    should_delete = True
                
                if should_delete:
                    to_delete.append(entity)
            
            # Delete in batches for better performance
            deleted_count = 0
            batch_size = 10
            for i in range(0, len(to_delete), batch_size):
                batch = to_delete[i:i + batch_size]
                tasks = [client.delete_dialog(entity) for entity in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                deleted_count += len(batch)
                await asyncio.sleep(1)  # Small delay between batches
            
            logging.info(f"Deleted {deleted_count} dialogs of type {dialog_type}")
            return deleted_count
            
    except Exception as e:
        logging.error(f"Error deleting dialogs: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to delete dialogs: {e}")

async def export_contacts(session_path: str, format_type: str = "txt") -> io.BytesIO:
    """Export contacts in various formats"""
    try:
        async with get_telegram_client(session_path) as client:
            contacts_result = await client(GetContactsRequest(hash=0))
            users = contacts_result.users
            
            if format_type == "json":
                contacts_data = []
                for user in users:
                    contacts_data.append({
                        "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                        "username": user.username or "",
                        "phone": user.phone or "",
                        "id": user.id,
                        "is_premium": getattr(user, "premium", False)
                    })
                
                content = json.dumps(contacts_data, indent=2, ensure_ascii=False)
                file_obj = io.BytesIO(content.encode("utf-8"))
                file_obj.name = "contacts.json"
                
            else:  # txt format
                lines = []
                for user in users:
                    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    username = user.username or ""
                    phone = user.phone or ""
                    lines.append(f"{name}\t{username}\t{phone}")
                
                content = "\n".join(lines) if lines else "No contacts found"
                file_obj = io.BytesIO(content.encode("utf-8"))
                file_obj.name = "contacts.txt"
            
            logging.info(f"Exported {len(users)} contacts in {format_type} format")
            return file_obj
            
    except Exception as e:
        logging.error(f"Error exporting contacts: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to export contacts: {e}")

async def import_contacts(session_path: str, contacts_data: List[Dict[str, str]]) -> int:
    """Import contacts from data"""
    try:
        async with get_telegram_client(session_path) as client:
            input_contacts = []
            for i, contact in enumerate(contacts_data):
                if contact.get("phone"):
                    input_contacts.append(InputPhoneContact(
                        client_id=i,
                        phone=contact["phone"],
                        first_name=contact.get("first_name", ""),
                        last_name=contact.get("last_name", "")
                    ))
            
            if input_contacts:
                result = await client(ImportContactsRequest(input_contacts))
                imported_count = len(result.imported)
                logging.info(f"Imported {imported_count} contacts")
                return imported_count
            return 0
            
    except Exception as e:
        logging.error(f"Error importing contacts: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to import contacts: {e}")

async def get_channel_members(session_path: str, channel_link: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Extract members from a channel/group"""
    try:
        async with get_telegram_client(session_path) as client:
            entity = await client.get_entity(channel_link)
            members = []
            
            async for user in client.iter_participants(entity, limit=limit):
                if isinstance(user, User):
                    members.append({
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": user.phone,
                        "is_bot": user.bot,
                        "is_premium": getattr(user, "premium", False)
                    })
            
            logging.info(f"Extracted {len(members)} members from {sanitize_log_input(channel_link)}")
            return members
            
    except Exception as e:
        logging.error(f"Error extracting members: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to extract members: {e}")

async def scrape_channel_messages(session_path: str, channel_link: str, 
                                limit: int = 100, offset_date: datetime = None) -> List[Dict[str, Any]]:
    """Scrape messages from a channel"""
    try:
        async with get_telegram_client(session_path) as client:
            entity = await client.get_entity(channel_link)
            messages = []
            
            async for message in client.iter_messages(entity, limit=limit, offset_date=offset_date):
                if message.message:
                    messages.append({
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.message,
                        "views": getattr(message, "views", 0),
                        "forwards": getattr(message, "forwards", 0),
                        "replies": getattr(message.replies, "replies", 0) if message.replies else 0
                    })
            
            logging.info(f"Scraped {len(messages)} messages from {sanitize_log_input(channel_link)}")
            return messages
            
    except Exception as e:
        logging.error(f"Error scraping messages: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to scrape messages: {e}")

async def check_crypto_wallet(session_path: str) -> str:
    """Check cryptocurrency wallet balance"""
    try:
        async with get_telegram_client(session_path) as client:
            try:
                wallet_bot = await client.get_entity("wallet")
                await client.send_message(wallet_bot, "/balance")
                await asyncio.sleep(3)
                
                messages = await client.get_messages(wallet_bot, limit=1)
                if messages and messages[0].message:
                    return messages[0].message
                return "No wallet information available"
                
            except Exception:
                return "Wallet bot not accessible"
                
    except Exception as e:
        logging.error(f"Crypto wallet check error: {sanitize_log_input(str(e))}")
        return f"Error checking wallet: {e}"

async def monitor_keywords(session_path: str, keywords: List[str], channels: List[str]) -> List[Dict[str, Any]]:
    """Monitor keywords in specified channels"""
    try:
        async with get_telegram_client(session_path) as client:
            matches = []
            
            for channel_link in channels:
                try:
                    entity = await client.get_entity(channel_link)
                    async for message in client.iter_messages(entity, limit=50):
                        if message.message:
                            message_text = message.message.lower()
                            for keyword in keywords:
                                if keyword.lower() in message_text:
                                    matches.append({
                                        "channel": channel_link,
                                        "keyword": keyword,
                                        "message": message.message,
                                        "date": message.date.isoformat(),
                                        "message_id": message.id
                                    })
                except Exception as e:
                    logging.warning(f"Error monitoring {channel_link}: {e}")
                    continue
            
            logging.info(f"Found {len(matches)} keyword matches")
            return matches
            
    except Exception as e:
        logging.error(f"Error monitoring keywords: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to monitor keywords: {e}")

async def auto_leave_inactive_groups(session_path: str, days_inactive: int = 30) -> int:
    """Leave groups with no recent activity"""
    try:
        async with get_telegram_client(session_path) as client:
            dialogs = await client.get_dialogs()
            cutoff_date = datetime.now() - timedelta(days=days_inactive)
            left_count = 0
            
            for dialog in dialogs:
                if isinstance(dialog.entity, (Channel, Chat)) and not getattr(dialog.entity, "broadcast", False):
                    if dialog.date < cutoff_date:
                        try:
                            await client(LeaveChannelRequest(dialog.entity))
                            left_count += 1
                            await asyncio.sleep(2)  # Rate limiting
                        except Exception as e:
                            logging.warning(f"Failed to leave group {dialog.entity.id}: {e}")
            
            logging.info(f"Left {left_count} inactive groups")
            return left_count
            
    except Exception as e:
        logging.error(f"Error leaving inactive groups: {sanitize_log_input(str(e))}")
        raise TelegramAPIError(f"Failed to leave inactive groups: {e}")