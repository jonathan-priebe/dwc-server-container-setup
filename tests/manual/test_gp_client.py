#!/usr/bin/env python3
"""
Test client for GameSpy GP Server
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwc_server.protocol.gamespy_proto import parse_gamespy_message, build_gamespy_message


async def test_gp_server():
    """Test GP server with a simulated login"""
    
    print("🎮 Testing GameSpy GP Server")
    print("=" * 60)
    
    try:
        # Connect to GP server
        reader, writer = await asyncio.open_connection('localhost', 29900)
        print("✓ Connected to GP server")
        
        # Send login request
        login_msg = build_gamespy_message({
            'login': '',
            'challenge': 'testchallenge123',
            'user': '1234567890123',
            'response': 'dummyresponse',
            'firewall': '1',
            'port': '0',
            'productid': '0',
            'gamename': 'ADAJ',  # Pokemon Diamond
            'namespaceid': '0',
        })
        
        print(f"\n📤 Sending login request...")
        print(f"   User: 1234567890123")
        print(f"   Game: ADAJ (Pokemon Diamond)")
        
        writer.write(login_msg)
        await writer.drain()
        
        # Read challenge response
        response = await asyncio.wait_for(
            reader.readuntil(b'\\final\\'),
            timeout=5.0
        )
        
        parsed = parse_gamespy_message(response)
        
        print(f"\n📥 Received challenge:")
        print(f"   Challenge: {parsed.get('challenge', 'N/A')}")
        
        if parsed.get('lc') == '1':
            # Send response to challenge
            server_challenge = parsed.get('challenge', '')
            
            # Calculate response (simplified - real client would hash password)
            import hashlib
            response_hash = hashlib.md5(
                f"testpassword{server_challenge}".encode()
            ).hexdigest()
            
            login_response = build_gamespy_message({
                'login': '',
                'challenge': 'testchallenge123',
                'user': '1234567890123',
                'response': response_hash,
                'firewall': '1',
                'port': '0',
                'productid': '0',
                'gamename': 'ADAJ',
                'namespaceid': '0',
            })
            
            print(f"\n📤 Sending login response...")
            writer.write(login_response)
            await writer.drain()
            
            # Read final response
            response = await asyncio.wait_for(
                reader.readuntil(b'\\final\\'),
                timeout=5.0
            )
            
            parsed = parse_gamespy_message(response)
        
        print(f"\n📥 Received response:")
        for key, value in parsed.items():
            if key != 'final':
                print(f"   {key}: {value}")
        
        if 'lc' in parsed:
            print("\n✅ Login successful!")
            print(f"   Profile ID: {parsed.get('profileid', 'N/A')}")
            print(f"   Session Key: {parsed.get('sesskey', 'N/A')}")
            
            # Check friend code via API
            profile_id = parsed.get('profileid')
            if profile_id:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"http://localhost:8001/api/profiles/{profile_id}/"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            profile = await resp.json()
                            print(f"\n🎯 Friend Code: {profile.get('friend_code', 'N/A')}")
                            print(f"   Game ID: {profile.get('game_id', 'N/A')}")
        else:
            print("\n❌ Login failed!")
            print(f"   Error: {parsed.get('errmsg', 'Unknown error')}")
        
        # Close connection
        writer.close()
        await writer.wait_closed()
        print("\n✓ Connection closed")
        
    except asyncio.TimeoutError:
        print("\n❌ Timeout - no response from server")
    except ConnectionRefusedError:
        print("\n❌ Connection refused - is the GP server running?")
        print("   Start it with: python dwc_server/servers/gamespy/gp_server.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_gp_server())