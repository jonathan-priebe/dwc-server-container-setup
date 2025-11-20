"""
DLS1 Server (Download Server)

Handles DLC/Event distribution for Nintendo DS/Wii games.
Port: 9003
"""

import asyncio
import logging
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)


class DLS1Server:
    """DLC/Download Server implementation"""
    
    def __init__(self, config):
        self.config = config
        self.app = web.Application()
        self.runner = None
        self._setup_routes()
        
        logger.info("DLS1 Server initialized")
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_post('/download', self.handle_download)
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_get('/', self.handle_root)
    
    async def handle_download(self, request: web.Request) -> web.Response:
        """Handle download requests (DLC, events, etc.)"""
        
        try:
            data = await request.post()
            data_dict = dict(data)
            
            action = data_dict.get('action', '').lower()
            gamecd = data_dict.get('gamecd', '')
            
            logger.info(f"[DLS1] Download request: action={action}, game={gamecd}")
            
            if action == 'count':
                return await self._handle_count(data_dict)
            elif action == 'list':
                return await self._handle_list(data_dict)
            elif action == 'contents':
                return await self._handle_contents(data_dict)
            else:
                logger.warning(f"[DLS1] Unknown action: {action}")
                return web.Response(status=404)
        
        except Exception as e:
            logger.error(f"[DLS1] Error: {e}", exc_info=True)
            return web.Response(status=500)
    
    async def _handle_count(self, data: dict) -> web.Response:
        """Return count of available DLC"""
        # For now, return 0 (no DLC available)
        return web.Response(
            text='0',
            content_type='text/plain',
            headers={'X-DLS-Host': 'http://dls1.nintendowifi.net/'}
        )
    
    async def _handle_list(self, data: dict) -> web.Response:
        """Return list of available DLC"""
        # For now, return empty list
        return web.Response(
            text='',
            content_type='text/plain',
            headers={'X-DLS-Host': 'http://dls1.nintendowifi.net/'}
        )
    
    async def _handle_contents(self, data: dict) -> web.Response:
        """Return DLC content file"""
        # For now, return 404
        return web.Response(status=404)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check"""
        return web.json_response({
            'status': 'healthy',
            'service': 'DLS1',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    async def handle_root(self, request: web.Request) -> web.Response:
        """Root endpoint"""
        return web.Response(
            text='Nintendo DLS1 Server\n',
            content_type='text/plain'
        )
    
    async def start(self):
        """Start DLS1 server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(
            self.runner,
            self.config.DLS1_HOST,
            self.config.DLS1_PORT
        )
        await site.start()
        
        logger.info(
            f"🟢 DLS1 Server started on "
            f"{self.config.DLS1_HOST}:{self.config.DLS1_PORT}"
        )
    
    async def stop(self):
        """Stop DLS1 server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("DLS1 Server stopped")