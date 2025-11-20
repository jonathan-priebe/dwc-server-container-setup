"""
GameSpy GP (Presence) Server

Handles user authentication, profile management, and presence for Nintendo DS/Wii.
This is the main login server that clients connect to after NAS authentication.

Protocol: TCP on port 29900
Message Format: \\key\\value\\key\\value\\final\\

Commands:
    - login: User authentication with challenge-response
    - getprofile: Retrieve profile information
    - updatepro: Update profile fields (lastname, firstname, etc.)
    - status: Update online status
    - logout: End session

Authentication Flow:
    1. Server sends challenge on connect
    2. Client sends login with authtoken and response hash
    3. Server validates and returns profile_id, proof, and session key
    4. Client can now use other commands

Author: DWC Server Team
"""

import asyncio
import base64
import hashlib
import logging
import os
import random
import secrets
import string
from pathlib import Path

from aiohttp import ClientSession
from dotenv import load_dotenv

from dwc_server.protocol.gamespy_proto import parse_gamespy_message, build_gamespy_message
from dwc_server.utils.friendcode import generate_friend_code, format_friend_code
from dwc_server.utils.encoding import base32_encode

# Load environment variables
load_dotenv()

# Configuration from environment
API_BASE_URL = os.getenv('API_BASE_URL', 'http://admin:7999/api')
API_TIMEOUT = 5  # seconds

# GameSpy constants
GAMESPY_PRODUCT_ID = '11'  # Nintendo DS product ID
SESSION_KEY_LENGTH = 7  # Hex chars for numeric sesskey (max 268435455, fits in 32-bit signed int)

logger = logging.getLogger(__name__)


class GameSpyGPServer:
    """
    GameSpy Presence Server implementation.

    Handles user login, profile management, and session tracking.
    All data is stored via the Django Admin API.

    Attributes:
        config: Server configuration object
        api_url: URL of the Django Admin API
        challenges: Server challenges by client address
        session_mappings: Numeric sesskey to hex session_key mappings
    """

    def __init__(self, config, api_url: str = None):
        """
        Initialize GP Server.

        Args:
            config: Server configuration with GP_HOST and GP_PORT
            api_url: Base URL for the Django Admin API (defaults to API_BASE_URL env var)
        """
        self.config = config
        self.api_url = api_url or API_BASE_URL

        # Store challenges by address for proof calculation
        self.challenges = {}  # {addr: server_challenge}

        # Map numeric sesskey to hex session_key for lookups
        self.session_mappings = {}  # {numeric_sesskey: hex_session_key}

        logger.info(f"GP Server initialized - API: {self.api_url}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _decode_nas_base64(value: str) -> str:
        """
        Decode Base64 value from NAS login data.

        NAS uses '*' instead of '=' for padding.

        Args:
            value: Base64-encoded string with '*' padding

        Returns:
            Decoded string
        """
        if not value:
            return ''
        try:
            return base64.b64decode(value.replace('*', '=')).decode('utf-8')
        except Exception:
            return ''

    def _generate_proof(self, server_challenge: str, client_challenge: str,
                       nas_challenge: str, authtoken: str) -> str:
        """
        Generate authentication proof using GameSpy algorithm.

        Algorithm from dwc_network_server_emulator:
        proof = MD5(MD5(nas_challenge) + ' '*48 + authtoken + server_challenge + client_challenge + MD5(nas_challenge))

        Args:
            server_challenge: Challenge from GP server greeting
            client_challenge: Challenge from client login message
            nas_challenge: Challenge from NAS login response
            authtoken: Authentication token from NAS

        Returns:
            32-character hex MD5 proof
        """
        md5_nas = hashlib.md5(nas_challenge.encode()).hexdigest()
        proof_str = md5_nas + (' ' * 48) + authtoken + server_challenge + client_challenge + md5_nas
        return hashlib.md5(proof_str.encode()).hexdigest()

    def _generate_login_ticket(self) -> str:
        """
        Generate GameSpy login ticket.

        Uses GameSpy's custom Base64 encoding where +/= are replaced with []_.

        Returns:
            Encoded login ticket string
        """
        random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        encoded = base64.b64encode(random_str.encode()).decode()
        return encoded.replace('+', '[').replace('/', ']').replace('=', '_')

    def _sesskey_to_numeric(self, sesskey_hex: str) -> str:
        """
        Convert hex session key to numeric format for DS.

        Uses first 7 hex chars to ensure value fits in 32-bit signed int.

        Args:
            sesskey_hex: Hex session key string

        Returns:
            Numeric string representation
        """
        return str(int(sesskey_hex[:SESSION_KEY_LENGTH], 16))

    # -------------------------------------------------------------------------
    # Client Connection Handler
    # -------------------------------------------------------------------------

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Handle GameSpy GP client connection.

        Sends initial challenge, then processes commands until disconnect.

        Args:
            reader: Async stream reader
            writer: Async stream writer
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"[GP] Client connected: {addr}")

        try:
            # Send initial server challenge
            challenge = secrets.token_hex(8)
            self.challenges[addr] = challenge

            greeting = f"\\lc\\1\\challenge\\{challenge}\\id\\1\\final\\"
            writer.write(greeting.encode('latin-1'))
            await writer.drain()
            logger.debug(f"[GP] Sent challenge to {addr}")

            # Process commands
            while True:
                data = await reader.readuntil(b'\\final\\')

                if not data:
                    break

                logger.debug(f"[GP] Received from {addr}: {data}")

                # Parse and handle command
                msg = parse_gamespy_message(data)
                response = await self._handle_command(msg, addr)

                if response:
                    writer.write(response)
                    await writer.drain()
                    logger.debug(f"[GP] Sent response to {addr}")

        except asyncio.IncompleteReadError:
            logger.info(f"[GP] Client disconnected: {addr}")
        except Exception as e:
            logger.error(f"[GP] Error handling client {addr}: {e}", exc_info=True)
        finally:
            self.challenges.pop(addr, None)
            writer.close()
            await writer.wait_closed()
            logger.debug(f"[GP] Connection closed: {addr}")

    async def _handle_command(self, msg: dict, addr: tuple) -> bytes:
        """
        Dispatch command to appropriate handler.

        Args:
            msg: Parsed GameSpy message
            addr: Client address tuple

        Returns:
            Response bytes or None
        """
        if 'login' in msg:
            return await self._handle_login(msg, addr)
        elif 'getprofile' in msg:
            return await self._handle_getprofile(msg, addr)
        elif 'updatepro' in msg:
            return await self._handle_updatepro(msg, addr)
        elif 'logout' in msg:
            return await self._handle_logout(msg, addr)
        elif 'status' in msg:
            return await self._handle_status(msg, addr)
        else:
            logger.warning(f"[GP] Unknown command: {list(msg.keys())}")
            return None

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------

    async def _handle_login(self, msg: dict, addr: tuple) -> bytes:
        """
        Handle login command.

        For DS/Wii, uses simplified authentication:
        - Accept all logins with valid NAS token
        - Auto-generate profiles on first login
        - Return session key and proof

        Args:
            msg: Login message with challenge, authtoken, response, gamename
            addr: Client address

        Returns:
            Login response or error
        """
        client_challenge = msg.get('challenge', '')
        authtoken = msg.get('authtoken', msg.get('user', ''))
        gamename = msg.get('gamename', '')
        response_hash = msg.get('response', '')

        logger.info(f"[GP] Login attempt: game={gamename}")

        # Initial challenge request (no response yet)
        if not response_hash:
            server_challenge = secrets.token_hex(8).upper()
            return build_gamespy_message({
                'lc': '1',
                'challenge': server_challenge,
                'id': msg.get('id', '1'),
            })

        # Authenticate and get/create profile
        profile, nas_userid, nas_challenge = await self._get_or_create_profile(
            authtoken, gamename, authtoken
        )

        if not profile:
            logger.error(f"[GP] Login failed - no profile")
            return build_gamespy_message({
                'error': '',
                'err': '260',
                'fatal': '',
                'errmsg': 'Login failed'
            })

        # Create session
        session = await self._create_session(profile['profile_id'])
        if not session:
            logger.error(f"[GP] Login failed - session creation error")
            return build_gamespy_message({
                'error': '',
                'err': '260',
                'fatal': '',
                'errmsg': 'Session creation failed'
            })

        # Generate numeric session key
        sesskey_hex = session['session_key']
        sesskey_numeric = self._sesskey_to_numeric(sesskey_hex)
        self.session_mappings[sesskey_numeric] = sesskey_hex

        logger.debug(f"[GP] Session: {sesskey_numeric} -> {sesskey_hex[:16]}...")

        # Generate proof
        server_challenge = self.challenges.get(addr, '')
        proof = self._generate_proof(server_challenge, client_challenge, nas_challenge, authtoken)

        # Generate login ticket
        lt = self._generate_login_ticket()

        # Get uniquenick
        uniquenick = profile.get('uniquenick', '')
        if not uniquenick:
            logger.warning(f"[GP] Profile {profile['profile_id']} has no uniquenick")
            uniquenick = authtoken[:20]

        # Build response
        response = build_gamespy_message({
            'lc': '2',
            'sesskey': sesskey_numeric,
            'proof': proof,
            'userid': str(nas_userid),
            'profileid': str(profile['profile_id']),
            'uniquenick': uniquenick,
            'lt': lt,
            'id': msg.get('id', '1'),
        })

        logger.info(f"[GP] Login successful: profile_id={profile['profile_id']}, FC={profile.get('friend_code', 'N/A')}")

        return response

    async def _handle_getprofile(self, msg: dict, addr: tuple) -> bytes:
        """
        Handle getprofile command.

        Returns profile information including nick, email, location.

        Args:
            msg: Message with profileid
            addr: Client address

        Returns:
            Profile info response or error
        """
        profileid = msg.get('profileid', '')
        msg_id = msg.get('id', '1')

        logger.debug(f"[GP] Get profile: {profileid}")

        profile = await self._get_profile(profileid)
        if not profile:
            logger.warning(f"[GP] Profile {profileid} not found")
            return build_gamespy_message({
                'error': '',
                'err': '265',
                'errmsg': 'Profile not found',
                'id': msg_id,
            })

        # Get NAS userid for this profile
        user_id_numeric = await self._get_nas_userid(profile['user_id'])

        # Build response
        response_dict = {
            'pi': '',
            'profileid': str(profile['profile_id']),
            'nick': profile.get('uniquenick', ''),
            'userid': user_id_numeric,
            'email': f"{profile.get('uniquenick', '')}@nds",
            'sig': secrets.token_hex(16),
            'uniquenick': profile.get('uniquenick', ''),
            'pid': GAMESPY_PRODUCT_ID,
        }

        # Add optional fields
        if profile.get('lastname'):
            response_dict['lastname'] = profile['lastname']
        if profile.get('firstname'):
            response_dict['firstname'] = profile['firstname']

        # Location fields (always included)
        response_dict['lon'] = '0.000000'
        response_dict['lat'] = '0.000000'
        response_dict['loc'] = ''
        response_dict['id'] = msg_id

        return build_gamespy_message(response_dict)

    async def _handle_updatepro(self, msg: dict, addr: tuple) -> bytes:
        """
        Handle profile update command.

        Updates profile fields like lastname, firstname.
        NOTE: Does not send response (per GameSpy protocol).

        Args:
            msg: Message with sesskey and fields to update
            addr: Client address

        Returns:
            None (no response per protocol)
        """
        sesskey = msg.get('sesskey')
        if not sesskey:
            logger.warning(f"[GP] updatepro: No sesskey")
            return None

        session = await self._get_session(sesskey)
        if not session:
            logger.warning(f"[GP] updatepro: Invalid session")
            return None

        profile_id = session.get('profile_id') or session.get('profile_info', {}).get('profile_id')

        # Collect fields to update
        update_data = {}
        if 'lastname' in msg:
            update_data['lastname'] = msg['lastname']
        if 'firstname' in msg:
            update_data['firstname'] = msg['firstname']

        if update_data:
            logger.debug(f"[GP] Updating profile {profile_id}: {list(update_data.keys())}")
            await self._update_profile(profile_id, update_data)

        # No response per protocol
        return None

    async def _handle_status(self, msg: dict, addr: tuple) -> bytes:
        """
        Handle status update command.

        Updates online status. Does not send response (per GameSpy protocol).

        Args:
            msg: Message with sesskey, status, statstring, locstring
            addr: Client address

        Returns:
            None (no response per protocol)
        """
        sesskey = msg.get('sesskey')
        if not sesskey:
            return None

        session = await self._get_session(sesskey)
        if not session:
            return None

        status_code = msg.get('status', '0')
        status_str = msg.get('statstring', '')
        loc_str = msg.get('locstring', '')

        logger.debug(f"[GP] Status: code={status_code}, stat={status_str}, loc={loc_str}")

        # TODO: Implement buddy list notifications
        return None

    async def _handle_logout(self, msg: dict, addr: tuple) -> bytes:
        """
        Handle logout command.

        Deletes session from database.

        Args:
            msg: Message with sesskey
            addr: Client address

        Returns:
            None
        """
        sesskey = msg.get('sesskey')
        if sesskey:
            await self._delete_session(sesskey)
            logger.info(f"[GP] Logout: session {sesskey}")

        return None

    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------

    async def _get_or_create_profile(self, userid: str, gamename: str, authtoken: str) -> tuple:
        """
        Get existing profile or create new one.

        Args:
            userid: User ID (authtoken)
            gamename: Game name from client
            authtoken: NAS authentication token

        Returns:
            Tuple of (profile_dict, nas_userid, nas_challenge)
        """
        try:
            async with ClientSession() as session:
                # Get NAS login data
                nas_data = await self._fetch_nas_login(session, authtoken)

                gsbrcd = self._decode_nas_base64(nas_data.get('gsbrcd', ''))
                nas_userid = self._decode_nas_base64(nas_data.get('userid', '')) or userid
                nas_challenge = nas_data.get('challenge', '')

                # Extract game_id from gsbrcd
                if gsbrcd and len(gsbrcd) >= 4:
                    game_id = gsbrcd[:4].upper()
                else:
                    game_id = gamename[:4].upper() if len(gamename) >= 4 else gamename.upper()

                logger.debug(f"[GP] game_id={game_id}, gsbrcd={gsbrcd}")

                # Try to find existing profile
                url = f"{self.api_url}/profiles/"
                params = {'user_id': userid, 'game_id': game_id}

                async with session.get(url, params=params, timeout=API_TIMEOUT) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('results'):
                            profile = data['results'][0]
                            logger.debug(f"[GP] Found profile: {profile['profile_id']}")
                            return profile, nas_userid, nas_challenge

                # Generate uniquenick
                try:
                    userid_int = int(nas_userid) if nas_userid.isdigit() else hash(nas_userid) & 0x7FFFFFFF
                except:
                    userid_int = hash(nas_userid) & 0x7FFFFFFF

                uniquenick = (base32_encode(userid_int) + gsbrcd)[:50]
                logger.debug(f"[GP] Generated uniquenick: {uniquenick}")

                # Create new profile
                profile_data = {
                    'user_id': userid,
                    'game_id': game_id,
                    'enabled': True,
                    'uniquenick': uniquenick,
                    'gs_broadcast_code': gsbrcd,
                }

                async with session.post(url, json=profile_data, timeout=API_TIMEOUT) as resp:
                    if resp.status == 201:
                        profile = await resp.json()
                        logger.info(f"[GP] Created profile: {profile['profile_id']}, FC={profile.get('friend_code', 'N/A')}")
                        return profile, nas_userid, nas_challenge
                    else:
                        error = await resp.text()
                        logger.warning(f"[GP] Failed to create profile: {resp.status} - {error}")

        except Exception as e:
            logger.error(f"[GP] Error in get_or_create_profile: {e}")

        return None, userid, ""

    async def _fetch_nas_login(self, session: ClientSession, authtoken: str) -> dict:
        """
        Fetch NAS login data for authtoken.

        Args:
            session: aiohttp ClientSession
            authtoken: NAS authentication token

        Returns:
            NAS login data dict or empty dict
        """
        try:
            url = f"{self.api_url}/nas-logins/"
            params = {'auth_token': authtoken}

            async with session.get(url, params=params, timeout=API_TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get('results', [])
                    if results:
                        return results[0].get('data', {})
        except Exception as e:
            logger.error(f"[GP] Error fetching NAS login: {e}")

        return {}

    async def _get_nas_userid(self, user_id: str) -> str:
        """
        Get numeric NAS userid for a profile's user_id.

        Args:
            user_id: Profile's user_id (authtoken)

        Returns:
            Numeric userid string
        """
        try:
            async with ClientSession() as session:
                nas_data = await self._fetch_nas_login(session, user_id)
                userid_b64 = nas_data.get('userid', '')
                if userid_b64:
                    decoded = self._decode_nas_base64(userid_b64)
                    if decoded:
                        return decoded
        except Exception as e:
            logger.error(f"[GP] Error getting NAS userid: {e}")

        # Fallback to hash
        return str(int(hashlib.md5(user_id.encode()).hexdigest()[:12], 16))

    async def _get_profile(self, profileid: str) -> dict:
        """
        Get profile by ID.

        Args:
            profileid: Profile ID

        Returns:
            Profile dict or None
        """
        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/profiles/{profileid}/"
                async with session.get(url, timeout=API_TIMEOUT) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"[GP] Error getting profile: {e}")

        return None

    async def _update_profile(self, profile_id: int, data: dict) -> bool:
        """
        Update profile fields.

        Args:
            profile_id: Profile ID
            data: Fields to update

        Returns:
            True if successful
        """
        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/profiles/{profile_id}/"
                async with session.patch(url, json=data, timeout=API_TIMEOUT) as resp:
                    return resp.status in [200, 204]
        except Exception as e:
            logger.error(f"[GP] Error updating profile: {e}")

        return False

    async def _create_session(self, profile_id: int) -> dict:
        """
        Create new session for profile.

        Args:
            profile_id: Profile ID

        Returns:
            Session dict or None
        """
        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/sessions/"
                data = {'profile_id': profile_id}

                async with session.post(url, json=data, timeout=API_TIMEOUT) as resp:
                    if resp.status == 201:
                        return await resp.json()
        except Exception as e:
            logger.error(f"[GP] Error creating session: {e}")

        return None

    async def _get_session(self, session_key: str) -> dict:
        """
        Get session by key.

        Args:
            session_key: Numeric sesskey or hex session_key

        Returns:
            Session dict or None
        """
        actual_key = self.session_mappings.get(session_key, session_key)

        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/sessions/{actual_key}/"
                async with session.get(url, timeout=API_TIMEOUT) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"[GP] Error getting session: {e}")

        return None

    async def _delete_session(self, session_key: str) -> bool:
        """
        Delete session.

        Args:
            session_key: Numeric sesskey or hex session_key

        Returns:
            True if deleted
        """
        actual_key = self.session_mappings.get(session_key, session_key)

        try:
            async with ClientSession() as session:
                url = f"{self.api_url}/sessions/{actual_key}/"
                async with session.delete(url, timeout=API_TIMEOUT) as resp:
                    if resp.status == 204:
                        self.session_mappings.pop(session_key, None)
                        return True
        except Exception as e:
            logger.error(f"[GP] Error deleting session: {e}")

        return False

    # -------------------------------------------------------------------------
    # Server Lifecycle
    # -------------------------------------------------------------------------

    async def start(self):
        """Start GP server and begin listening for connections."""
        server = await asyncio.start_server(
            self.handle_client,
            self.config.GP_HOST,
            self.config.GP_PORT
        )

        logger.info(f"GP Server started on {self.config.GP_HOST}:{self.config.GP_PORT}")

        return server


# -----------------------------------------------------------------------------
# Standalone Execution
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    from dwc_server.config import config

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        server_instance = GameSpyGPServer(config)
        server = await server_instance.start()

        print("\n" + "=" * 60)
        print("GameSpy GP Server Running")
        print("=" * 60)
        print(f"Listening on: {config.GP_HOST}:{config.GP_PORT}")
        print("\nPress Ctrl+C to stop")
        print("=" * 60 + "\n")

        async with server:
            try:
                await server.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down...")

    asyncio.run(main())
