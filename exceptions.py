"""
Custom exceptions for SessionMaster
"""

class SessionMasterError(Exception):
    """Base exception for SessionMaster"""
    pass

class ConfigurationError(SessionMasterError):
    """Configuration related errors"""
    pass

class TelegramAPIError(SessionMasterError):
    """Telegram API related errors"""
    pass

class SessionError(SessionMasterError):
    """Session related errors"""
    pass

class AuthenticationError(SessionMasterError):
    """Authentication related errors"""
    pass