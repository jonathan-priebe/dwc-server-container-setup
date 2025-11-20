"""
GameSpy NAT Negotiation Server

Handles NAT traversal for peer-to-peer connections.
This allows DS/Wii consoles behind NATs to connect to each other.

Protocol: UDP
Port: 27901 (default)
"""

import asyncio
import logging
import struct
import time
from pathlib import Path
from aiohttp import ClientSession

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class GameSpyNatNegServer:
    """GameSpy NAT Negotiation Server implementation"""

    # NAT Negotiation packet types
    NATNEG_INIT = 0x00
    NATNEG_INITACK = 0x01
    NATNEG_ERTTEST = 0x02
    NATNEG_ERTACK = 0x03
    NATNEG_STATEUPDATE = 0x04
    NATNEG_CONNECT = 0x05
    NATNEG_CONNECT_ACK = 0x06
    NATNEG_CONNECT_PING = 0x07
    NATNEG_BACKUP_TEST = 0x08
    NATNEG_BACKUP_ACK = 0x09
    NATNEG_ADDRESS_CHECK = 0x0A
    NATNEG_ADDRESS_REPLY = 0x0B
    NATNEG_NATIFY_REQUEST = 0x0C
    NATNEG_REPORT = 0x0D
    NATNEG_REPORT_ACK = 0x0E
    NATNEG_PREINIT = 0x0F
    NATNEG_PREINIT_ACK = 0x10

    def __init__(self, config, api_url='http://admin:7999/api'):
        self.config = config
        self.api_url = api_url
        self.port = getattr(config, 'NATNEG_PORT', 27901)

        # NAT negotiation sessions (cookie -> session info)
        self.sessions = {}

        logger.info(f"NAT Negotiation Server initialized - API: {self.api_url}")

    class NatNegProtocol(asyncio.DatagramProtocol):
        """UDP Protocol handler for NAT Negotiation"""

        def __init__(self, server_instance):
            self.server = server_instance
            super().__init__()

        def connection_made(self, transport):
            self.transport = transport
            logger.debug("[NATNEG] Protocol ready")

        def datagram_received(self, data, addr):
            """Handle incoming NAT negotiation packet"""
            asyncio.create_task(self.server.handle_packet(data, addr, self.transport))

    async def handle_packet(self, data: bytes, addr: tuple, transport):
        """Handle NAT negotiation packet"""

        if len(data) < 8:
            logger.warning(f"[NATNEG] Packet too short from {addr}: {len(data)} bytes")
            return

        try:
            # Parse packet header
            # Format: [magic:6][version:1][packettype:1][cookie:4][...]
            magic = data[0:6]
            version = data[6]
            packet_type = data[7]

            # Check magic number
            if magic != b'\xFD\xFC\x1E\x66\x6A\xB2':
                logger.warning(f"[NATNEG] Invalid magic from {addr}: {magic.hex()}")
                return

            logger.debug(f"[NATNEG] Packet from {addr}: type=0x{packet_type:02x}, version={version}")

            # Handle packet types
            if packet_type == self.NATNEG_INIT:
                await self._handle_init(data, addr, transport)
            elif packet_type == self.NATNEG_ERTTEST:
                await self._handle_erttest(data, addr, transport)
            elif packet_type == self.NATNEG_ADDRESS_CHECK:
                await self._handle_address_check(data, addr, transport)
            elif packet_type == self.NATNEG_REPORT:
                await self._handle_report(data, addr, transport)
            elif packet_type == self.NATNEG_CONNECT:
                await self._handle_connect(data, addr, transport)
            else:
                logger.debug(f"[NATNEG] Unhandled packet type: 0x{packet_type:02x}")

        except Exception as e:
            logger.error(f"[NATNEG] Error handling packet from {addr}: {e}", exc_info=True)

    async def _handle_init(self, data: bytes, addr: tuple, transport):
        """
        Handle NATNEG_INIT packet

        Client initiates NAT negotiation
        """
        if len(data) < 16:
            return

        # Parse cookie (4 bytes at offset 8)
        cookie = struct.unpack('<I', data[8:12])[0]

        logger.info(f"[NATNEG] INIT from {addr}: cookie={cookie}")

        # Store session
        self.sessions[cookie] = {
            'cookie': cookie,
            'client_addr': addr[0],
            'client_port': addr[1],
            'init_time': time.time()
        }

        # Store in database via API
        await self._store_natneg_session(cookie, addr[0], addr[1])

        # Send INITACK
        response = bytearray(data[0:8])  # Copy header
        response[7] = self.NATNEG_INITACK  # Change packet type
        response.extend(data[8:])  # Copy rest

        transport.sendto(bytes(response), addr)
        logger.debug(f"[NATNEG] Sent INITACK to {addr}")

    async def _handle_erttest(self, data: bytes, addr: tuple, transport):
        """
        Handle NATNEG_ERTTEST (ERT = External Reachability Test)

        Tests if client is reachable from outside
        """
        if len(data) < 16:
            return

        cookie = struct.unpack('<I', data[8:12])[0]

        logger.debug(f"[NATNEG] ERTTEST from {addr}: cookie={cookie}")

        # Send ERTACK
        response = bytearray(data[0:8])
        response[7] = self.NATNEG_ERTACK
        response.extend(data[8:])

        transport.sendto(bytes(response), addr)
        logger.debug(f"[NATNEG] Sent ERTACK to {addr}")

    async def _handle_address_check(self, data: bytes, addr: tuple, transport):
        """
        Handle NATNEG_ADDRESS_CHECK

        Client asks for its external IP/port
        """
        if len(data) < 16:
            return

        cookie = struct.unpack('<I', data[8:12])[0]

        logger.debug(f"[NATNEG] ADDRESS_CHECK from {addr}: cookie={cookie}")

        # Build ADDRESS_REPLY
        response = bytearray(data[0:8])
        response[7] = self.NATNEG_ADDRESS_REPLY
        response.extend(data[8:12])  # Cookie

        # Add client's external IP (4 bytes)
        ip_parts = addr[0].split('.')
        for part in ip_parts:
            response.append(int(part))

        # Add client's external port (2 bytes, big endian)
        response.extend(struct.pack('>H', addr[1]))

        transport.sendto(bytes(response), addr)
        logger.info(f"[NATNEG] Sent ADDRESS_REPLY to {addr}: {addr[0]}:{addr[1]}")

    async def _handle_report(self, data: bytes, addr: tuple, transport):
        """
        Handle NATNEG_REPORT

        Client reports NAT negotiation result
        """
        if len(data) < 16:
            return

        cookie = struct.unpack('<I', data[8:12])[0]

        # Parse result if available
        result = data[12] if len(data) > 12 else 0

        logger.info(f"[NATNEG] REPORT from {addr}: cookie={cookie}, result={result}")

        # Send REPORT_ACK
        response = bytearray(data[0:8])
        response[7] = self.NATNEG_REPORT_ACK
        response.extend(data[8:12])  # Cookie

        transport.sendto(bytes(response), addr)
        logger.debug(f"[NATNEG] Sent REPORT_ACK to {addr}")

        # Clean up session
        if cookie in self.sessions:
            del self.sessions[cookie]
            logger.debug(f"[NATNEG] Cleaned up session {cookie}")

    async def _handle_connect(self, data: bytes, addr: tuple, transport):
        """
        Handle NATNEG_CONNECT

        Client requests connection to another client
        """
        if len(data) < 16:
            return

        cookie = struct.unpack('<I', data[8:12])[0]

        logger.debug(f"[NATNEG] CONNECT from {addr}: cookie={cookie}")

        # Send CONNECT_ACK
        response = bytearray(data[0:8])
        response[7] = self.NATNEG_CONNECT_ACK
        response.extend(data[8:])

        transport.sendto(bytes(response), addr)
        logger.debug(f"[NATNEG] Sent CONNECT_ACK to {addr}")

    async def _store_natneg_session(self, cookie: int, client_addr: str, client_port: int):
        """Store NAT negotiation session in database via API"""

        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/natneg/"  # We need to add this endpoint
                data = {
                    'cookie': cookie,
                    'client_addr': client_addr,
                    'client_port': client_port
                }

                async with session.post(url, json=data, timeout=5) as resp:
                    if resp.status == 201:
                        logger.debug(f"[NATNEG] Stored session: cookie={cookie}")
                    else:
                        logger.warning(f"[NATNEG] Failed to store session: {resp.status}")

        except Exception as e:
            logger.error(f"[NATNEG] API error: {e}")

    async def start(self):
        """Start NAT Negotiation server"""

        loop = asyncio.get_event_loop()

        # Create UDP endpoint
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: self.NatNegProtocol(self),
            local_addr=(self.config.GP_HOST, self.port)  # Use same host as GP
        )

        logger.info(
            f"🟢 NAT Negotiation Server started on "
            f"{self.config.GP_HOST}:{self.port} (UDP)"
        )

        return transport


if __name__ == '__main__':
    # Test NAT server standalone
    from dwc_server.config import config

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        server = GameSpyNatNegServer(config)
        await server.start()

        print("\n" + "="*60)
        print("🎮 NAT Negotiation Server Running")
        print("="*60)
        print(f"Listening on: {config.GP_HOST}:{server.port} (UDP)")
        print("\nWaiting for NAT negotiation packets...")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")

    asyncio.run(main())
