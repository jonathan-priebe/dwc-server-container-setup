"""
Main entry point for DWC GameSpy Server

Starts all GameSpy servers:
- NAS (Nintendo Authentication Server)
- GP (GameSpy Presence)
- QR (Query & Reporting)
- DLS1 (Download/DLC Server)
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dwc_server.config import config
from dwc_server.servers.nas_server import NASServer
from dwc_server.servers.gamespy.gp_server import GameSpyGPServer
from dwc_server.servers.gamespy.qr_server import GameSpyQRServer
from dwc_server.servers.gamespy.natneg_server import GameSpyNatNegServer
from dwc_server.servers.dls1_server import DLS1Server
from dwc_server.servers.storage_server import StorageServer

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class DWCServerManager:
    """Manages all DWC servers"""
    
    def __init__(self):
        self.config = config
        self.servers = {}
        self.running = False
    
    async def start_all(self):
        """Start all servers"""
        
        print("\n" + "="*70)
        print("🎮 DWC Server - Nintendo Wi-Fi Connection Emulator")
        print("="*70)
        print()
        
        try:
            # Start NAS Server
            print("📡 Starting NAS Server...")
            nas_server = NASServer(self.config, self.config.DATABASE_URL)
            await nas_server.start()
            self.servers['nas'] = nas_server
            print(f"   ✓ NAS Server running on port {self.config.NAS_PORT}")
            
            # Start GP Server
            print("\n🎯 Starting GP Server...")
            gp_server = GameSpyGPServer(self.config, self.config.DATABASE_URL)
            gp_task = await gp_server.start()
            self.servers['gp'] = gp_task
            print(f"   ✓ GP Server running on port {self.config.GP_PORT}")
            
            # Start QR Server
            print("\n📊 Starting QR Server...")
            qr_server = GameSpyQRServer(self.config, self.config.DATABASE_URL)
            qr_transport = await qr_server.start()
            self.servers['qr'] = qr_transport
            print(f"   ✓ QR Server running on port {self.config.QR_PORT} (UDP)")

            # Start NAT Negotiation Server
            print("\n🔀 Starting NAT Negotiation Server...")
            natneg_server = GameSpyNatNegServer(self.config, self.config.DATABASE_URL)
            natneg_transport = await natneg_server.start()
            self.servers['natneg'] = natneg_transport
            print(f"   ✓ NAT Negotiation Server running on port {natneg_server.port} (UDP)")

            # Start DLS1 Server
            print("\n📦 Starting DLS1 Server...")
            dls1_server = DLS1Server(self.config)
            await dls1_server.start()
            self.servers['dls1'] = dls1_server  # ← STORE IT!
            print(f"   ✓ DLS1 Server running on port {self.config.DLS1_PORT}")
            
            # Start Storage Server
            print("\n💾 Starting Storage Server...")
            storage_server = StorageServer(self.config, self.config.DATABASE_URL)
            await storage_server.start()
            self.servers['storage'] = storage_server
            print(f"   ✓ Storage Server running on port 8001")

            print("\n" + "="*70)
            print("✅ All servers started successfully!")
            print("="*70)
            print()
            print("📋 Server Status:")
            print(f"   NAS:     http://{self.config.NAS_HOST}:{self.config.NAS_PORT}/ac")
            print(f"   GP:      {self.config.GP_HOST}:{self.config.GP_PORT} (TCP)")
            print(f"   QR:      {self.config.QR_HOST}:{self.config.QR_PORT} (UDP)")
            print(f"   NATNEG:  {self.config.GP_HOST}:27901 (UDP)")
            print(f"   DLS1:    http://{self.config.DLS1_HOST}:{self.config.DLS1_PORT}/download")
            print()
            print("🔗 Admin Panel:")
            print(f"   http://admin:7999/admin")
            print()
            print("📊 API:")
            print(f"   http://admin:7999/api")
            print()
            print("⚠️  Note: Django admin server must be started separately:")
            print("   cd admin_panel && python manage.py runserver 8001")
            print()
            print("Press Ctrl+C to stop all servers")
            print("="*70)
            print()
            
            self.running = True
            
            # Keep running
            await asyncio.Event().wait()
        
        except Exception as e:
            logger.error(f"Error starting servers: {e}", exc_info=True)
            await self.stop_all()
            raise
    
    async def stop_all(self):
        """Stop all servers gracefully"""
        
        if not self.running:
            return
        
        print("\n" + "="*70)
        print("🛑 Shutting down servers...")
        print("="*70)
        
        # Stop NAS
        if 'nas' in self.servers:
            print("   Stopping NAS Server...")
            await self.servers['nas'].stop()
        
        # Stop GP (it's a server object, need to close it)
        if 'gp' in self.servers:
            print("   Stopping GP Server...")
            self.servers['gp'].close()
            await self.servers['gp'].wait_closed()
        
        # Stop QR (it's a transport)
        if 'qr' in self.servers:
            print("   Stopping QR Server...")
            self.servers['qr'].close()

        # Stop NAT Negotiation (it's a transport)
        if 'natneg' in self.servers:
            print("   Stopping NAT Negotiation Server...")
            self.servers['natneg'].close()

        # Stop DLS1
        if 'dls1' in self.servers:
            print("   Stopping DLS1 Server...")
            await self.servers['dls1'].stop()

        # Stop Storage
        if 'storage' in self.servers:
            print("   Stopping Storage Server...")
            await self.servers['storage'].stop()
        
        print("\n✅ All servers stopped")
        print("="*70)
        
        self.running = False


async def main():
    """Main entry point"""
    
    manager = DWCServerManager()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(manager.stop_all())
    
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(manager.stop_all()))
    
    try:
        await manager.start_all()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await manager.stop_all()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")