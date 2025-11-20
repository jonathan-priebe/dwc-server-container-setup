"""
Storage Server - Friend Code Management

Provides HTTP API for profile and friend code management.
Communicates with Django Admin API for database operations.

Port: 8000 (internal - not exposed to internet)
"""

import asyncio
import logging
from aiohttp import web, ClientSession
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)
API_BASE_URL = os.getenv('API_BASE_URL', 'http://admin:7999/api')

class StorageServer:
    """Storage Server for Friend Code management"""
    
    def __init__(self, config, api_url: str = None):
        self.config = config
        self.api_url = api_url or API_BASE_URL
        self.app = web.Application()
        self.runner = None
        self._setup_routes()

        # API Token for authentication
        self.api_token = os.getenv('NAS_API_TOKEN', '')
        self.api_headers = {
            'Authorization': f'Token {self.api_token}'
        } if self.api_token else {}

        logger.info(f"Storage Server initialized - API: {self.api_url}")

    def _setup_routes(self):
        """Setup HTTP routes"""
        # Profile management
        self.app.router.add_get('/profile', self.handle_get_profile)
        self.app.router.add_post('/profile', self.handle_create_profile)

        # Health check
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_get('/', self.handle_root)

    async def handle_get_profile(self, request: web.Request) -> web.Response:
        """
        Get profile by userid and gamecd

        Query params:
        - userid: User ID
        - gamecd: Game ID (e.g., APAD)

        Returns:
        - profile_id
        - friend_code (formatted XXXX-XXXX-XXXX)
        - user_id
        - game_id
        """
        try:
            userid = request.query.get('userid')
            gamecd = request.query.get('gamecd')

            if not userid or not gamecd:
                return web.json_response({
                    'error': 'Missing userid or gamecd'
                }, status=400)

            logger.info(f"[Storage] Get profile: userid={userid}, game={gamecd}")

            # Query Django API
            async with ClientSession() as session:
                url = f"{self.api_url}/profiles/?user_id={userid}&game_id={gamecd}"
                async with session.get(url, headers=self.api_headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Check if profile exists (DRF returns list)
                        if data and len(data) > 0:
                            profile = data[0]

                            logger.info(f"[Storage] Profile found: {profile['profile_id']}")

                            return web.json_response({
                                'profile_id': profile['profile_id'],
                                'friend_code': profile.get('friend_code', 'N/A'),
                                'user_id': profile['user_id'],
                                'game_id': profile['game_id'],
                                'enabled': profile.get('enabled', True),
                                'gs_broadcast_code': profile.get('gs_broadcast_code', ''),
                                'uniquenick': profile.get('uniquenick', '')
                            })
                        else:
                            logger.info(f"[Storage] Profile not found for {userid}/{gamecd}")
                            return web.json_response({
                                'error': 'Profile not found'
                            }, status=404)
                    else:
                        error_text = await resp.text()
                        logger.error(f"[Storage] API error: {resp.status} - {error_text}")
                        return web.json_response({
                            'error': f'API error: {resp.status}'
                        }, status=500)

        except Exception as e:
            logger.error(f"[Storage] Error getting profile: {e}", exc_info=True)
            return web.json_response({
                'error': str(e)
            }, status=500)

    async def handle_create_profile(self, request: web.Request) -> web.Response:
        """
        Create new profile

        POST body:
        {
            "user_id": "...",
            "game_id": "APAD",
            "mac_address": "00:09:BF:11:22:33"
        }

        Returns:
        - profile_id
        - friend_code (formatted)
        """
        try:
            data = await request.json()

            userid = data.get('user_id')
            gamecd = data.get('game_id')
            mac = data.get('mac_address')

            if not userid or not gamecd:
                return web.json_response({
                    'error': 'Missing user_id or game_id'
                }, status=400)

            logger.info(f"[Storage] Create profile: userid={userid}, game={gamecd}")

            # First, get console by MAC
            console_id = None
            if mac:
                async with ClientSession() as session:
                    # Get console by MAC address
                    url = f"{self.api_url}/consoles/{mac}/"
                    async with session.get(url, headers=self.api_headers, timeout=5) as resp:
                        if resp.status == 200:
                            console_data = await resp.json()
                            # Console API returns full object, get mac_address as identifier
                            console_id = console_data.get('mac_address')
                            logger.debug(f"[Storage] Found console: {console_id}")

            # Create profile via Django API
            profile_data = {
                'user_id': userid,
                'game_id': gamecd[:4],  # Ensure 4 chars for friend code algorithm
                'enabled': True
            }

            # Console field is a ForeignKey, so we need the PK
            # But our API uses MAC as lookup_field
            # So we need to find the console's PK first
            if console_id:
                async with ClientSession() as session:
                    url = f"{self.api_url}/consoles/{console_id}/"
                    async with session.get(url, headers=self.api_headers, timeout=5) as resp:
                        if resp.status == 200:
                            console_obj = await resp.json()
                            # Get the actual PK (id field)
                            # Note: Our Console model doesn't have explicit 'id'
                            # but Django creates it automatically
                            # For now, we'll pass the mac_address and let DRF handle it
                            profile_data['console'] = console_id

            async with ClientSession() as session:
                url = f"{self.api_url}/profiles/"
                async with session.post(
                    url,
                    json=profile_data,
                    headers=self.api_headers,
                    timeout=5
                ) as resp:
                    if resp.status == 201:
                        profile = await resp.json()

                        logger.info(
                            f"[Storage] Profile created: {profile['profile_id']} "
                            f"Friend Code: {profile.get('friend_code', 'N/A')}"
                        )

                        return web.json_response({
                            'profile_id': profile['profile_id'],
                            'friend_code': profile.get('friend_code', 'N/A'),
                            'user_id': profile['user_id'],
                            'game_id': profile['game_id']
                        }, status=201)
                    else:
                        error_text = await resp.text()
                        logger.error(f"[Storage] Failed to create profile: {resp.status} - {error_text}")
                        return web.json_response({
                            'error': f'Failed to create profile: {error_text}'
                        }, status=resp.status)

        except Exception as e:
            logger.error(f"[Storage] Error creating profile: {e}", exc_info=True)
            return web.json_response({
                'error': str(e)
            }, status=500)

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'Storage',
            'timestamp': datetime.utcnow().isoformat()
        })

    async def handle_root(self, request: web.Request) -> web.Response:
        """Root endpoint"""
        return web.Response(
            text='DWC Storage Server\n',
            content_type='text/plain'
        )

    async def start(self):
        """Start Storage server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        # Listen on port 8000 (like original!)
        site = web.TCPSite(
            self.runner,
            '0.0.0.0',
            8000  # ← CHANGED from 8001
        )
        await site.start()
        
        logger.info("🟢 Storage Server started on 0.0.0.0:8000")

    async def stop(self):
        """Stop Storage server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Storage Server stopped")

if __name__ == '__main__':
    # Test standalone
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from dwc_server.config import config
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        server = StorageServer(config)
        await server.start()
        
        print("\n" + "="*60)
        print("💾 Storage Server Running")
        print("="*60)
        print("Listening on: http://0.0.0.0:8001")
        print("\nEndpoints:")
        print("  GET  /profile?userid=X&gamecd=Y")
        print("  POST /profile")
        print("  GET  /health")
        print("\nPress Ctrl+C to stop")
        print("="*60 + "\n")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            await server.stop()
    
    asyncio.run(main())