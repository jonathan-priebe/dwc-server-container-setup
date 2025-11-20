"""
GameSpy QR (Query & Reporting) Server

Handles UDP-based game server registration and queries for Nintendo DS/Wii.

Protocol: UDP
Port: 27900 (default)

Functions:
- Game server registration and heartbeat
- Server browser queries
- Challenge-response authentication
- Server list management

Communication Flow:
1. Client sends heartbeat (0x03) with server info
2. Server responds with challenge (0x01)
3. Client sends challenge response (0x01)
4. Server sends client registered (0x0A)
5. Server is now listed in database
"""

import asyncio
import base64
import logging
import os
import secrets
import struct

from aiohttp import ClientSession

from dwc_server.protocol.gamespy_proto import build_gamespy_message, parse_gamespy_message


# =============================================================================
# Configuration
# =============================================================================

API_BASE_URL = os.getenv('API_BASE_URL', 'http://admin:7999/api')
API_TIMEOUT = 5  # seconds

# RC4 constants
RC4_STATE_SIZE = 0x100  # 256 bytes for RC4 state array

# Packet type constants (client -> server)
PACKET_TYPE_QUERY = 0x00
PACKET_TYPE_CHALLENGE = 0x01
PACKET_TYPE_HEARTBEAT = 0x03
PACKET_TYPE_CLIENT_ACK = 0x07
PACKET_TYPE_KEEPALIVE = 0x08
PACKET_TYPE_AVAILABLE = 0x09

# Response type constants (server -> client)
RESPONSE_TYPE_CHALLENGE = 0x01
RESPONSE_TYPE_REGISTERED = 0x0A

# Response header for server packets
RESPONSE_HEADER = bytes([0xFE, 0xFD])

# Server state constants
STATE_RUNNING = '0'
STATE_CHANGED = '1'
STATE_SHUTDOWN = '2'
STATE_STARTING = '3'

logger = logging.getLogger(__name__)


# =============================================================================
# GameSpy Secret Keys
# =============================================================================

# Format: game_id -> secret_key
SECRET_KEYS = {
    'pokemondpds': '1vTlwb',
    'pokemonpltnds': '1vTlwb',
    'pokemonhgssds': '1vTlwb',
    'maboroshids': '4L63vN',
    'mariokartds': 'Rq3nxS',
    'mkds': 'Rq3nxS',
    'metaboroshids': 'x5J1Xg',
    'tetrisds': 'uC6fNE',
    # Add more games as needed
}


# =============================================================================
# RC4 Encryption Functions
# =============================================================================

def rc4_encrypt(key: bytes, data: bytes) -> bytes:
    """
    RC4 encryption (modified version used by GameSpy).

    This is a modified RC4 implementation based on Tetris DS overlay 10 @ 0216E9B8.
    The modification is in the PRGA phase where the input byte affects the index.

    Args:
        key: Encryption key
        data: Data to encrypt

    Returns:
        Encrypted data
    """
    key = bytearray(key)
    data = bytearray(data)

    if len(key) == 0:
        return bytes(data)

    # Key-scheduling algorithm (KSA)
    S = list(range(RC4_STATE_SIZE))

    j = 0
    for i in range(RC4_STATE_SIZE):
        j = (j + S[i] + key[i % len(key)]) & 0xFF
        S[i], S[j] = S[j], S[i]

    # Pseudo-random generation algorithm (PRGA) + encryption
    # Modified: input byte affects index i
    i = 0
    j = 0
    for x, val in enumerate(data):
        i = (i + 1 + val) & 0xFF  # Modified RC4: add input byte
        j = (j + S[i]) & 0xFF
        S[i], S[j] = S[j], S[i]
        data[x] ^= S[(S[i] + S[j]) & 0xFF]

    return bytes(data)


def prepare_rc4_base64(key: str, data: str) -> bytes:
    """
    Prepare RC4 encrypted base64 string (GameSpy variant).

    Encrypts data with RC4, appends null terminator, and base64 encodes.

    Args:
        key: Encryption key string
        data: Data string to encrypt

    Returns:
        Base64 encoded encrypted data
    """
    encrypted = rc4_encrypt(key.encode('ascii'), data.encode('ascii'))
    encrypted = bytearray(encrypted)
    encrypted.append(0)  # Null terminator
    return base64.b64encode(bytes(encrypted))


# =============================================================================
# Session Class
# =============================================================================

class QRSession:
    """
    QR Server session for tracking client state.

    Each session represents a game server that has connected and is going
    through the challenge-response authentication process.
    """

    def __init__(self, address: tuple):
        """
        Initialize a new QR session.

        Args:
            address: Client address tuple (ip, port)
        """
        self.session = 0
        self.challenge = ""
        self.secretkey = ""
        self.sent_challenge = False
        self.heartbeat_data = None
        self.address = address
        self.console = 0
        self.playerid = 0
        self.gamename = ""


# =============================================================================
# QR Server Implementation
# =============================================================================

class GameSpyQRServer:
    """
    GameSpy Query & Reporting Server implementation.

    Handles UDP communication with Nintendo DS/Wii clients for game server
    registration and server browser functionality.
    """

    def __init__(self, config, api_url: str = None):
        """
        Initialize QR server.

        Args:
            config: Server configuration object
            api_url: Optional API URL override (defaults to API_BASE_URL)
        """
        self.config = config
        self.api_url = api_url or API_BASE_URL

        # Sessions by session_id
        self.sessions = {}

        logger.info(f"QR Server initialized - API: {self.api_url}")

    # =========================================================================
    # UDP Protocol Handler
    # =========================================================================

    class QRProtocol(asyncio.DatagramProtocol):
        """UDP Protocol handler for QR server."""

        def __init__(self, server_instance):
            self.server = server_instance
            super().__init__()

        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            """Handle incoming UDP datagram."""
            asyncio.create_task(self.server.handle_message(data, addr, self.transport))

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(self, data: bytes, addr: tuple, transport):
        """
        Handle incoming QR message.

        Routes messages to appropriate handlers based on packet type.

        Args:
            data: Raw packet data
            addr: Client address tuple
            transport: UDP transport for sending responses
        """
        try:
            # Check if this is a binary Nintendo DS packet
            # Client packets do NOT have 0xFE 0xFD prefix
            if len(data) > 0 and data[0] in [
                PACKET_TYPE_QUERY, PACKET_TYPE_CHALLENGE, PACKET_TYPE_HEARTBEAT,
                PACKET_TYPE_CLIENT_ACK, PACKET_TYPE_KEEPALIVE, PACKET_TYPE_AVAILABLE
            ]:
                await self._handle_binary_packet(data, addr, transport)
                return

            # Try to parse as text GameSpy message
            msg = parse_gamespy_message(data)

            if not msg:
                logger.warning(f"[QR] Empty message from {addr}, raw data length: {len(data)}")
                logger.debug(f"[QR] Raw data (hex): {data.hex()}")
                return

            logger.debug(f"[QR] Received from {addr}: {msg}")

            # Handle different message types
            if 'heartbeat' in msg:
                await self._handle_heartbeat(msg, addr, transport)
            elif 'available' in msg:
                await self._handle_available(msg, addr, transport)
            elif 'challenge' in msg:
                await self._handle_challenge(msg, addr, transport)
            else:
                logger.warning(f"[QR] Unknown message type: {msg}")

        except Exception as e:
            logger.error(f"[QR] Error handling message from {addr}: {e}", exc_info=True)

    # =========================================================================
    # Binary Packet Handlers
    # =========================================================================

    async def _handle_binary_packet(self, data: bytes, addr: tuple, transport):
        """
        Handle binary Nintendo DS/Wii packets.

        Nintendo DS sends binary packets with command byte first (NO 0xFE 0xFD prefix):
        - 0x00: Query
        - 0x01: Challenge response
        - 0x03: Heartbeat
        - 0x07: Client message ack
        - 0x08: Keep alive
        - 0x09: Available query

        Server responses have 0xFE 0xFD prefix, but client packets don't.

        Args:
            data: Raw packet data
            addr: Client address tuple
            transport: UDP transport
        """
        if len(data) == 0:
            return

        packet_type = data[0]
        data_offset = 1

        # Extract session ID (little endian) for most commands
        session_id = None
        session_id_raw = None
        if packet_type != PACKET_TYPE_AVAILABLE and len(data) >= data_offset + 4:
            session_id = struct.unpack("<I", data[data_offset:data_offset+4])[0]
            session_id_raw = data[data_offset:data_offset+4]

        logger.debug(
            f"[QR] Binary packet from {addr}: type=0x{packet_type:02x}, "
            f"session={session_id if session_id else 0:08x}, length={len(data)}"
        )

        # Calculate payload offset (after command and session_id)
        payload_offset = data_offset + 4

        if packet_type == PACKET_TYPE_QUERY:
            logger.debug(f"[QR] Query from {addr}: {data[payload_offset:]}")

        elif packet_type == PACKET_TYPE_CHALLENGE:
            await self._handle_challenge_response(
                data, addr, transport, session_id, session_id_raw, payload_offset
            )

        elif packet_type == PACKET_TYPE_HEARTBEAT:
            await self._handle_ds_heartbeat(
                data, addr, transport, session_id, session_id_raw, payload_offset
            )

        elif packet_type == PACKET_TYPE_CLIENT_ACK:
            logger.debug(f"[QR] Client message ack from {addr}")

        elif packet_type == PACKET_TYPE_KEEPALIVE:
            logger.debug(f"[QR] Keep alive from {addr}")

        elif packet_type == PACKET_TYPE_AVAILABLE:
            await self._handle_ds_available(data, addr, transport)

        else:
            logger.warning(f"[QR] Unknown binary packet type: 0x{packet_type:02x}")
            logger.debug(f"[QR] Raw data (hex): {data.hex()}")

    async def _handle_ds_available(self, data: bytes, addr: tuple, transport):
        """
        Handle Nintendo DS "available" query.

        Format:
        - Byte 0: 0x09 (packet type)
        - Bytes 1-4: Challenge (big endian)
        - Bytes 5-16: Game ID (12 bytes, null-terminated)

        Args:
            data: Raw packet data
            addr: Client address tuple
            transport: UDP transport
        """
        if len(data) < 17:
            logger.warning(f"[QR] DS available packet too short: {len(data)} bytes")
            return

        try:
            # Parse challenge (big endian)
            challenge = struct.unpack('>I', data[1:5])[0]

            # Parse game ID (12 bytes, may contain nulls)
            game_id_bytes = data[5:17]
            game_id = game_id_bytes.rstrip(b'\x00').decode('ascii', errors='ignore')

            logger.info(f"[QR] DS Available query from {addr}: game={game_id}, challenge={challenge}")

            # Look up available servers for this game
            servers = await self._get_available_servers(game_id)

            if servers:
                response = self._build_ds_available_response(challenge, servers)
                transport.sendto(response, addr)
                logger.info(f"[QR] Sent {len(servers)} server(s) to {addr}")
            else:
                # No servers available - send empty response
                response = struct.pack('>BBI H', 0xFE, 0xFD, challenge, 0)
                transport.sendto(response, addr)
                logger.info(f"[QR] No servers available for {game_id}")

        except Exception as e:
            logger.error(f"[QR] Error handling DS available: {e}", exc_info=True)

    async def _handle_ds_heartbeat(self, data: bytes, addr: tuple, transport,
                                    session_id: int, session_id_raw: bytes, payload_offset: int):
        """
        Handle Nintendo DS heartbeat (0x03).

        Format:
        [0xFE 0xFD] 0x03 [session_id (4 bytes)] [NULL-separated key-value pairs]

        Keys include: localip0, localport, natneg, statechanged, gamename,
        publicip, publicport, etc.

        Args:
            data: Raw packet data
            addr: Client address tuple
            transport: UDP transport
            session_id: Session identifier
            session_id_raw: Raw session ID bytes
            payload_offset: Offset to payload data
        """
        if len(data) < payload_offset + 1:
            logger.warning(f"[QR] Heartbeat too short: {len(data)} bytes")
            return

        # Create or get session
        if session_id not in self.sessions:
            self.sessions[session_id] = QRSession(addr)
            self.sessions[session_id].session = session_id
            logger.debug(f"[QR] Created new session {session_id:08x} for {addr}")

        session = self.sessions[session_id]
        session.address = addr  # Update address (may change between packets)

        # Parse heartbeat data
        heartbeat_data = data[payload_offset:]
        k = self._parse_heartbeat_data(heartbeat_data)

        gamename = k.get('gamename', 'unknown')
        statechanged = k.get('statechanged', STATE_RUNNING)
        localport = k.get('localport', '0')

        logger.info(
            f"[QR] [{addr[0]}:{addr[1]} {session_id:08x}] Heartbeat from "
            f"{addr[0]}:{localport}: game={gamename}, state={statechanged}"
        )
        logger.debug(f"[QR] Heartbeat data: {k}")

        # Check if server is shutting down
        if statechanged == STATE_SHUTDOWN:
            logger.info(f"[QR] Server {session_id:08x} shutting down")
            if session_id in self.sessions:
                del self.sessions[session_id]
            # TODO: Remove server from database
            return

        # Get secret key for this game
        if gamename in SECRET_KEYS:
            session.secretkey = SECRET_KEYS[gamename]
        else:
            logger.warning(f"[QR] No secret key for game: {gamename}")

        session.gamename = gamename

        # Handle publicip - if it's "0", use the actual address
        if k.get('publicip') == '0':
            ip_parts = [int(x) for x in addr[0].split('.')]
            k['publicip'] = str(struct.unpack('<I', bytes(ip_parts))[0])

        # Handle publicport mismatch
        if 'publicport' in k and 'localport' in k and k['publicport'] != k['localport']:
            logger.debug(
                f"[QR] publicport {k['publicport']} doesn't match localport "
                f"{k['localport']}, changing to {addr[1]}"
            )
            k['publicport'] = str(addr[1])

        # If challenge already sent, just update server list
        if session.sent_challenge:
            logger.debug(f"[QR] Challenge already sent, updating server list")
            await self._update_server_list(session_id, k)
        else:
            # Send challenge to client
            challenge = self._generate_challenge(addr)
            session.challenge = challenge

            packet = bytearray([0xFE, 0xFD, RESPONSE_TYPE_CHALLENGE])
            packet.extend(session_id_raw)
            packet.extend(challenge.encode('ascii'))
            packet.append(0x00)

            transport.sendto(bytes(packet), addr)
            logger.info(f"[QR] [{addr[0]}:{addr[1]} {session_id:08x}] Sent challenge: {challenge}")

            session.sent_challenge = True
            session.heartbeat_data = k

    async def _handle_challenge_response(self, data: bytes, addr: tuple, transport,
                                          session_id: int, session_id_raw: bytes, payload_offset: int):
        """
        Handle challenge response (0x01).

        Client sends back the challenge response after receiving our challenge.
        If valid, we send 0x0A (client registered).

        Args:
            data: Raw packet data
            addr: Client address tuple
            transport: UDP transport
            session_id: Session identifier
            session_id_raw: Raw session ID bytes
            payload_offset: Offset to payload data
        """
        if len(data) < payload_offset:
            logger.warning(f"[QR] Challenge response too short: {len(data)} bytes")
            return

        # Extract client challenge response
        if len(data) > payload_offset and data[-1] == 0:
            client_response = data[payload_offset:-1]
        else:
            client_response = data[payload_offset:]

        logger.info(f"[QR] [{addr[0]}:{addr[1]} {session_id:08x}] Challenge response: {client_response}")

        # Get session
        if session_id not in self.sessions:
            logger.warning(f"[QR] No session for {session_id:08x}")
            return

        session = self.sessions[session_id]

        # Prepare expected challenge response
        expected_response = prepare_rc4_base64(session.secretkey, session.challenge)

        logger.info(f"[QR] Challenge validation: secretkey={session.secretkey}, challenge={session.challenge}")
        logger.info(f"[QR] Expected response: {expected_response}")
        logger.info(f"[QR] Client response:   {client_response}")

        # Compare challenge
        if client_response == expected_response:
            # Challenge succeeded - send client registered
            packet = bytearray([0xFE, 0xFD, RESPONSE_TYPE_REGISTERED])
            packet.extend(session_id_raw)

            transport.sendto(bytes(packet), addr)
            logger.info(f"[QR] [{addr[0]}:{addr[1]} {session_id:08x}] Sent client registered")

            # Update server list with heartbeat data
            if session.heartbeat_data is not None:
                asyncio.create_task(self._update_server_list(session_id, session.heartbeat_data))
        else:
            # Challenge failed
            logger.warning(f"[QR] [{addr[0]}:{addr[1]} {session_id:08x}] Challenge FAILED")
            logger.warning(f"[QR] Expected: {expected_response}, Got: {client_response}")
            # Reset sent_challenge so next heartbeat sends new challenge
            session.sent_challenge = False

    # =========================================================================
    # Text Message Handlers
    # =========================================================================

    async def _handle_heartbeat(self, msg: dict, addr: tuple, transport):
        """
        Handle heartbeat message from game server (text format).

        Heartbeats keep the server alive in the master server list.

        Expected fields:
        - heartbeat: Port number
        - gamename: Game identifier
        - statechanged: 0=running, 1=changed, 2=shutdown, 3=starting
        - numplayers: Current player count
        - maxplayers: Maximum players
        - hostname: Server name
        - mapname: Current map

        Args:
            msg: Parsed message dictionary
            addr: Client address tuple
            transport: UDP transport
        """
        gamename = msg.get('gamename', 'unknown')
        port = msg.get('heartbeat', '0')
        statechanged = msg.get('statechanged', '0')

        ip_address = addr[0]
        server_key = f"{ip_address}:{port}"

        logger.info(f"[QR] Heartbeat from {server_key}: game={gamename}, state={statechanged}")

        try:
            await self._update_server(ip_address, int(port), gamename, msg)
        except Exception as e:
            logger.error(f"[QR] Failed to update server: {e}")

    async def _handle_available(self, msg: dict, addr: tuple, transport):
        """
        Handle available query (text format).

        Client asks: "What servers are available for this game?"

        Args:
            msg: Parsed message dictionary
            addr: Client address tuple
            transport: UDP transport
        """
        gamename = msg.get('gamename', '')
        validate = msg.get('validate', '')

        logger.info(f"[QR] Available query from {addr}: game={gamename}")

        servers = await self._get_available_servers(gamename)

        if servers:
            response = self._build_available_response(servers, validate)
            transport.sendto(response.encode('latin-1'), addr)
        else:
            transport.sendto(b'\\final\\', addr)

    async def _handle_challenge(self, msg: dict, addr: tuple, transport):
        """
        Handle challenge request (text format).

        Args:
            msg: Parsed message dictionary
            addr: Client address tuple
            transport: UDP transport
        """
        logger.debug(f"[QR] Challenge request from {addr}")

        challenge = secrets.token_hex(8)

        response = build_gamespy_message({
            'challenge': challenge,
        })

        transport.sendto(response.encode('latin-1'), addr)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _parse_heartbeat_data(data: bytes) -> dict:
        """
        Parse NULL-separated key-value pairs from heartbeat data.

        Args:
            data: Raw heartbeat payload

        Returns:
            Dictionary of key-value pairs
        """
        parts = data.rstrip(b'\x00').split(b'\x00')

        result = {}
        for i in range(0, len(parts) - 1, 2):
            try:
                key = parts[i].decode('ascii', errors='ignore')
                value = parts[i + 1].decode('ascii', errors='ignore')
                result[key] = value
            except (IndexError, UnicodeDecodeError) as e:
                logger.warning(f"[QR] Error parsing heartbeat key-value: {e}")
                continue

        return result

    @staticmethod
    def _generate_challenge(addr: tuple) -> str:
        """
        Generate challenge string for client authentication.

        Format: <random_hex><00><ip_hex><port_hex>

        Args:
            addr: Client address tuple (ip, port)

        Returns:
            Challenge string
        """
        addr_hex = ''.join(["%02X" % int(x) for x in addr[0].split('.')])
        port_hex = "%04X" % addr[1]
        return secrets.token_hex(3) + '00' + addr_hex + port_hex

    async def _log_api_error(self, resp, operation: str):
        """
        Log API error response.

        Args:
            resp: aiohttp response object
            operation: Description of the operation that failed
        """
        try:
            error_data = await resp.json()
            logger.warning(f"[QR] {operation}: {resp.status} - {error_data}")
        except Exception:
            text = await resp.text()
            logger.warning(f"[QR] {operation}: {resp.status} - {text}")

    # =========================================================================
    # Server List Management
    # =========================================================================

    async def _update_server_list(self, session_id: int, k: dict):
        """
        Update server list from heartbeat data.

        Args:
            session_id: Session identifier
            k: Heartbeat data dictionary
        """
        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]
        statechanged = k.get('statechanged', STATE_RUNNING)

        if statechanged == STATE_SHUTDOWN:
            if session_id in self.sessions:
                del self.sessions[session_id]
            # TODO: Remove from database
        else:
            localport = int(k.get('localport', 0))
            await self._update_server_from_heartbeat(
                session.address[0],
                localport,
                k.get('gamename', 'unknown'),
                k,
                session_id
            )

    async def _update_server_from_heartbeat(self, ip: str, port: int, gamename: str,
                                             data: dict, session_id: int):
        """
        Update server in database from heartbeat data.

        Args:
            ip: Server IP address
            port: Server port
            gamename: Game name identifier
            data: Heartbeat data dictionary
            session_id: Session identifier
        """
        server_id = f"{session_id:08x}"

        server_data = {
            'server_id': server_id,
            'ip_address': ip,
            'port': port,
            'game_name': gamename,
            'max_players': int(data.get('maxplayers', 4)),
            'current_players': int(data.get('numplayers', 0)),
            'game_data': {k: v for k, v in data.items() if k not in ['dwc_pid', 'gamename']},
        }

        # Get dwc_pid (profile ID) from heartbeat if available
        dwc_pid = data.get('dwc_pid')
        if dwc_pid:
            server_data['host_profile'] = int(dwc_pid)

        logger.debug(f"[QR] Server data to register: {server_data}")

        async with ClientSession() as http_session:
            url = f"{self.api_url}/game-servers/{server_id}/"

            try:
                # First try PUT (update existing)
                async with http_session.put(url, json=server_data, timeout=API_TIMEOUT) as resp:
                    if resp.status in [200, 201]:
                        logger.info(f"[QR] Server updated: {server_id} ({ip}:{port})")
                    elif resp.status == 404:
                        # Server doesn't exist, create it
                        create_url = f"{self.api_url}/game-servers/"
                        async with http_session.post(create_url, json=server_data, timeout=API_TIMEOUT) as create_resp:
                            if create_resp.status in [200, 201]:
                                logger.info(f"[QR] Server registered: {server_id} ({ip}:{port})")
                            else:
                                await self._log_api_error(create_resp, "Failed to register server")
                    else:
                        await self._log_api_error(resp, "Failed to update server")
            except Exception as e:
                logger.error(f"[QR] API error: {e}")

    async def _get_available_servers(self, game_id: str) -> list:
        """
        Get available servers for a game from API.

        Args:
            game_id: Game identifier

        Returns:
            List of server dictionaries with 'ip', 'port', 'name' keys
        """
        try:
            async with ClientSession() as http_session:
                url = f"{self.api_url}/game-servers/"
                params = {'game_name': game_id}

                async with http_session.get(url, params=params, timeout=API_TIMEOUT) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Handle DRF pagination response
                        if isinstance(data, dict):
                            data = data.get('results', [])

                        if not isinstance(data, list):
                            logger.warning(f"[QR] Unexpected API response type: {type(data)}")
                            return []

                        # Build server list
                        online_servers = []
                        for server in data:
                            if not isinstance(server, dict):
                                logger.warning(f"[QR] Invalid server data: {type(server)}")
                                continue

                            server_info = {
                                'ip': server.get('ip_address', '0.0.0.0'),
                                'port': server.get('port', 0),
                                'name': server.get('server_name', 'Unknown'),
                            }
                            online_servers.append(server_info)

                        logger.debug(f"[QR] Found {len(online_servers)} servers for {game_id}")
                        return online_servers
                    else:
                        logger.warning(f"[QR] API returned {resp.status}")
                        return []

        except Exception as e:
            logger.error(f"[QR] Failed to get servers: {e}", exc_info=True)
            return []

    async def _update_server(self, ip: str, port: int, gamename: str, data: dict):
        """
        Update server via API (text format heartbeat).

        Args:
            ip: Server IP address
            port: Server port
            gamename: Game name identifier
            data: Heartbeat message dictionary
        """
        server_data = {
            'ip_address': ip,
            'port': port,
            'game_name': gamename,
            'server_name': data.get('hostname', f'{gamename} Server'),
            'current_players': int(data.get('numplayers', 0)),
            'max_players': int(data.get('maxplayers', 0)),
            'game_mode': data.get('gamemode', ''),
            'map_name': data.get('mapname', ''),
        }

        async with ClientSession() as http_session:
            url = f"{self.api_url}/game-servers/"

            try:
                async with http_session.post(url, json=server_data, timeout=API_TIMEOUT) as resp:
                    if resp.status in [200, 201]:
                        logger.debug(f"[QR] Server registered: {ip}:{port}")
                    else:
                        logger.warning(f"[QR] Failed to register server: {resp.status}")
            except Exception as e:
                logger.error(f"[QR] API error: {e}")

    # =========================================================================
    # Response Builders
    # =========================================================================

    def _build_ds_available_response(self, challenge: int, servers: list) -> bytes:
        """
        Build Nintendo DS available response.

        Format:
        - Bytes 0-1: 0xFE 0xFD (response header)
        - Bytes 2-5: Challenge (big endian)
        - Bytes 6-7: Server count (big endian uint16)
        - For each server: IP (4 bytes) + Port (big endian uint16)

        Args:
            challenge: Challenge value from request
            servers: List of server dictionaries

        Returns:
            Binary response data
        """
        response = bytearray()

        # Header
        response.extend(RESPONSE_HEADER)

        # Challenge
        response.extend(struct.pack('>I', challenge))

        # Server count
        response.extend(struct.pack('>H', len(servers)))

        # Server list
        for server in servers:
            # Parse IP address
            ip_parts = server['ip'].split('.')
            if len(ip_parts) == 4:
                response.extend([int(p) for p in ip_parts])
            else:
                response.extend([0, 0, 0, 0])

            # Port
            response.extend(struct.pack('>H', server['port']))

        return bytes(response)

    def _build_available_response(self, servers: list, validate: str = '') -> str:
        """
        Build available response (text format).

        Args:
            servers: List of server dictionaries
            validate: Optional validation token

        Returns:
            GameSpy formatted response string
        """
        response_parts = []

        for server in servers:
            response_parts.append(f"\\ip\\{server['ip']}")
            response_parts.append(f"\\port\\{server['port']}")
            response_parts.append(f"\\hostname\\{server['name']}")

        if validate:
            response_parts.append(f"\\validate\\{validate}")

        response_parts.append('\\final\\')

        return ''.join(response_parts)

    # =========================================================================
    # Server Lifecycle
    # =========================================================================

    async def start(self):
        """
        Start QR server.

        Creates UDP endpoint and begins listening for messages.

        Returns:
            UDP transport object
        """
        loop = asyncio.get_event_loop()

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: self.QRProtocol(self),
            local_addr=(self.config.QR_HOST, self.config.QR_PORT)
        )

        logger.info(
            f"QR Server started on "
            f"{self.config.QR_HOST}:{self.config.QR_PORT} (UDP)"
        )

        return transport

    async def stop(self):
        """Stop QR server and cleanup resources."""
        logger.info("QR Server stopped")


# =============================================================================
# Standalone Test
# =============================================================================

if __name__ == '__main__':
    from dwc_server.config import config

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        server = GameSpyQRServer(config)
        await server.start()

        print("\n" + "="*60)
        print("QR Server Running")
        print("="*60)
        print(f"Listening on: {config.QR_HOST}:{config.QR_PORT} (UDP)")
        print("\nWaiting for queries...")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            await server.stop()

    asyncio.run(main())
