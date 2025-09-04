#!/usr/bin/env python3
"""
Test script for phone authentication
"""

import asyncio
from auth_manager import auth_manager

async def test_auth():
    user_id = 123456789
    phone = "+1234567890"  # Replace with test phone
    
    print("Testing phone authentication...")
    
    # Start phone auth
    result = await auth_manager.start_phone_auth(user_id, phone)
    print(f"Start auth result: {result}")
    
    if result['success']:
        # Simulate code input
        code = input("Enter verification code: ")
        
        result = await auth_manager.verify_code(user_id, code)
        print(f"Code verification result: {result}")
        
        if result['success'] and result['step'] == '2fa':
            # Need 2FA
            password = input("Enter 2FA password: ")
            
            result = await auth_manager.verify_2fa(user_id, password)
            print(f"2FA verification result: {result}")

if __name__ == "__main__":
    asyncio.run(test_auth())