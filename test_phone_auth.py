#!/usr/bin/env python3
"""
Test phone authentication functionality
"""

import asyncio
from config import config
from auth_manager import auth_manager

async def test_phone_auth():
    """Test phone authentication"""
    print("Testing phone authentication...")
    
    # Test with a phone number
    phone = "+918459770125"
    user_id = 123456789  # Test user ID
    
    print(f"Starting auth for {phone}")
    result = auth_manager.start_phone_auth(user_id, phone)
    
    print(f"Result: {result}")
    
    if result['success']:
        print("✅ Phone auth started successfully")
        print(f"Message: {result['message']}")
    else:
        print("❌ Phone auth failed")
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_phone_auth())