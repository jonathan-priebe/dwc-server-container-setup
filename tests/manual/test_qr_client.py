#!/usr/bin/env python3
"""
Test client for GameSpy QR Server

Simulates a game server sending heartbeats
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwc_server.protocol.gamespy_proto import build_gamespy_message


async def test_qr_server():
    """Test QR server with simulated game server heartbeat"""
    
    print("🎮 Testing GameSpy QR Server")
    print("=" * 60)
    
    try:
        # Create UDP socket
        loop = asyncio.get_running_loop()
        
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: asyncio.DatagramProtocol(),
            remote_addr=('localhost', 27900)
        )
        
        print("✓ Connected to QR server (UDP)")
        
        # Send heartbeat (game server registration)
        heartbeat_msg = build_gamespy_message({
            'heartbeat': '27000',  # Server port
            'gamename': 'pokemondpds',
            'statechanged': '3',  # Starting up
            'hostname': 'Test Pokemon Server',
            'numplayers': '2',
            'maxplayers': '4',
            'gamemode': 'battle',
            'mapname': 'test_map',
            'password': '0',
        })
        
        print(f"\n📤 Sending heartbeat...")
        print(f"   Game: pokemondpds")
        print(f"   Server: Test Pokemon Server")
        print(f"   Players: 2/4")
        
        transport.sendto(heartbeat_msg)
        
        # Wait a bit
        await asyncio.sleep(1)
        
        print(f"\n✅ Heartbeat sent!")
        print(f"   Server should now be visible in API")
        
        # Check via API
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = "http://localhost:8001/api/game-servers/"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    servers = data.get('results', [])
                    
                    print(f"\n📊 Active Game Servers: {len(servers)}")
                    for server in servers[-3:]:  # Show last 3
                        print(f"\n   Server: {server['server_id']}")
                        print(f"   Game: {server['game_name']}")
                        print(f"   Address: {server['address']}")
                        print(f"   Players: {server['current_players']}/{server['max_players']}")
                        print(f"   Online: {'✓' if server['is_online'] else '✗'}")
        
        # Send another heartbeat (update)
        print(f"\n📤 Sending update heartbeat...")
        
        update_msg = build_gamespy_message({
            'heartbeat': '27000',
            'gamename': 'pokemondpds',
            'statechanged': '1',  # State changed
            'hostname': 'Test Pokemon Server',
            'numplayers': '3',  # Player joined!
            'maxplayers': '4',
            'gamemode': 'battle',
        })
        
        transport.sendto(update_msg)
        await asyncio.sleep(1)
        
        print(f"✅ Update sent! Players: 3/4")
        
        # Close
        transport.close()
        print("\n✓ Connection closed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_qr_server())