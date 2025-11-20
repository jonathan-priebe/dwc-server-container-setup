"""
Nintendo Authentication Server (NAS)

This server handles the initial authentication for Nintendo DS/Wii consoles.
It's the first contact point when a DS/Wii connects to Wi-Fi features and
returns authentication tokens and GameSpy server information.

Protocol: HTTP POST to /ac
Endpoints:
    - POST /ac: Main authentication endpoint
    - GET /: Connection test
    - GET /health: Health check

Actions:
    - LOGIN: Initial authentication, returns token and challenge
    - SVCLOC: Service location lookup (DLC servers, etc.)
    - ACCTCREATE: Account creation (auto-approved)

Author: DWC Server Team
"""

import asyncio
import base64
import logging
import os
import secrets
import string
from datetime import datetime
from pathlib import Path

from aiohttp import web, ClientSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
API_BASE_URL = os.getenv('API_BASE_URL', 'http://admin:7999/api')
API_TIMEOUT = 5  # seconds

logger = logging.getLogger(__name__)


class NASServer:
    """
    Nintendo Authentication Server implementation.

    Handles initial DS/Wii authentication and returns GameSpy connection info.
    All console and login data is stored via the Django Admin API.

    Attributes:
        config: Server configuration object
        api_url: URL of the Django Admin API
        app: aiohttp web application
        api_headers: Headers for API authentication
    """

    def __init__(self, config, api_url: str = None):
        """
        Initialize NAS Server.

        Args:
            config: Server configuration with NAS_HOST and NAS_PORT
            api_url: Base URL for the Django Admin API (defaults to API_BASE_URL env var)
        """
        self.config = config
        self.api_url = api_url or API_BASE_URL
        self.app = web.Application()
        self.runner = None
        self._setup_routes()

        # Setup API authentication
        nas_api_token = os.getenv('NAS_API_TOKEN')
        if not nas_api_token:
            logger.error("NAS_API_TOKEN not set in environment. API access will fail.")
            nas_api_token = 'INVALID_TOKEN'

        self.api_headers = {
            'Authorization': f'Token {nas_api_token}'
        }

        logger.info(f"NAS Server initialized - API: {self.api_url}")

    def _setup_routes(self):
        """Setup HTTP routes for NAS endpoints."""
        # Root endpoints (connection test)
        self.app.router.add_get('/', self.handle_root)
        self.app.router.add_post('/', self.handle_root)

        # Main authentication endpoint
        self.app.router.add_get('/ac', self.handle_ac)
        self.app.router.add_post('/ac', self.handle_ac)

        # Health check
        self.app.router.add_get('/health', self.handle_health)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _format_mac_address(mac_raw: str) -> str:
        """
        Format MAC address to standard XX:XX:XX:XX:XX:XX format.

        Args:
            mac_raw: Raw MAC address (may contain colons, dashes, or be plain)

        Returns:
            Formatted MAC address with colons

        Example:
            >>> NASServer._format_mac_address("001122334455")
            '00:11:22:33:44:55'
        """
        mac_clean = mac_raw.replace(':', '').replace('-', '').upper()

        if len(mac_clean) == 12:
            return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
        return mac_raw

    @staticmethod
    def _extract_client_ip(ip_header: str) -> str:
        """
        Extract the real client IP from X-Forwarded-For header.

        Handles proxy chains where the header contains multiple IPs.

        Args:
            ip_header: Raw IP or X-Forwarded-For header value

        Returns:
            Clean client IP address

        Example:
            >>> NASServer._extract_client_ip("192.168.1.1, 10.0.0.1")
            '192.168.1.1'
        """
        if ',' in ip_header:
            return ip_header.split(',')[0].strip()
        return str(ip_header).strip()

    def _decode_param(self, param: str) -> str:
        """
        Decode a Base64-encoded parameter from the DS/Wii.

        Nintendo uses a custom Base64 variant with '*' as padding instead of '='.
        Device names may be UTF-16-LE encoded.

        Args:
            param: Base64-encoded parameter value

        Returns:
            Decoded string value
        """
        if not param:
            return ''

        # Remove custom padding character ('*')
        clean_param = param.rstrip('*')

        # Add standard Base64 padding
        padding_needed = len(clean_param) % 4
        if padding_needed:
            clean_param += '=' * (4 - padding_needed)

        try:
            # Handle URL-safe Base64 variants
            decoded_bytes = base64.b64decode(
                clean_param.replace('-', '+').replace('_', '/'),
                validate=False
            )

            # Try UTF-8 first, then UTF-16-LE for device names
            try:
                return decoded_bytes.decode('utf-8').replace('\x00', '').strip()
            except UnicodeDecodeError:
                return decoded_bytes.decode('utf-16-le').replace('\x00', '').strip()

        except Exception as e:
            logger.warning(f"[NAS] Failed to decode param '{param}': {e}")
            return param

    def _build_nas_response(self, params: dict) -> web.Response:
        """
        Build NAS response in Nintendo's expected format.

        Format: key1=base64value1&key2=base64value2\\r\\n

        All values are Base64-encoded with '*' replacing '=' padding.
        This matches the original Python 2 dict_to_qs() function.

        Args:
            params: Dictionary of response parameters

        Returns:
            aiohttp Response with encoded body
        """
        encoded_params = {}
        for key, value in params.items():
            value_str = str(value)
            value_b64 = base64.b64encode(value_str.encode('utf-8'))
            encoded_params[key] = value_b64.decode('utf-8').replace('=', '*')

        # Build query string with CRLF terminator
        response_text = '&'.join(f"{k}={v}" for k, v in encoded_params.items())
        response_text += '\r\n'

        return web.Response(
            body=response_text.encode('utf-8'),
            content_type='text/plain',
            headers={'NODE': 'wifiappe1'}
        )

    def _generate_challenge(self) -> str:
        """
        Generate 8-character alphanumeric authentication challenge.

        Returns:
            Random challenge string (e.g., "B5N7XOHt")
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(8))

    def _generate_token(self, userid: str) -> str:
        """
        Generate URL-safe authentication token.

        Args:
            userid: User ID (currently unused, reserved for future use)

        Returns:
            44-character URL-safe token
        """
        return secrets.token_urlsafe(32)

    # -------------------------------------------------------------------------
    # Request Handlers
    # -------------------------------------------------------------------------

    async def handle_root(self, request: web.Request) -> web.Response:
        """
        Handle root request for connection testing.

        DS/Wii sends GET / to test connectivity before authentication.
        """
        logger.info(f"[NAS] Root request from {request.remote}")

        return web.Response(
            text='Nintendo Wi-Fi Connection\n',
            content_type='text/plain',
            status=200
        )

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        Health check endpoint for monitoring.

        Returns:
            JSON with status, service name, and timestamp
        """
        return web.json_response({
            'status': 'healthy',
            'service': 'NAS',
            'timestamp': datetime.utcnow().isoformat()
        })

    async def handle_ac(self, request: web.Request) -> web.Response:
        """
        Handle Nintendo Authentication requests.

        Main endpoint for DS/Wii authentication. Dispatches to specific
        handlers based on the 'action' parameter.

        Expected form data:
            - action: LOGIN, SVCLOC, or ACCTCREATE
            - userid: Console user ID
            - macadr: MAC address
            - devname: Device name (optional)
            - gamecd: Game code (optional)
        """
        raw_ip = request.headers.get("X-Forwarded-For", request.remote)
        client_ip = self._extract_client_ip(raw_ip)

        try:
            # Parse form data
            if request.method == 'POST':
                data = await request.post()
            else:
                data = request.query

            data_dict = dict(data)

            # Decode and dispatch action
            action_encoded = data_dict.get('action', '')
            action = self._decode_param(action_encoded).upper()

            logger.info(f"[NAS] {client_ip} - Action: {action}")
            logger.debug(f"[NAS] Data: {data_dict}")

            if action == 'LOGIN':
                return await self._handle_login(data_dict, client_ip)
            elif action == 'SVCLOC':
                return await self._handle_svcloc(data_dict, client_ip)
            elif action == 'ACCTCREATE':
                return await self._handle_acctcreate(data_dict, client_ip)
            else:
                logger.warning(f"[NAS] Unknown action: {action}")
                return self._build_nas_response({
                    'returncd': '110',
                    'locator': 'gamespy.com',
                })

        except Exception as e:
            logger.error(f"[NAS] Error handling request: {e}", exc_info=True)
            return self._build_nas_response({
                'returncd': '110',
                'locator': 'gamespy.com',
            })

    async def _handle_login(self, data: dict, client_ip: str) -> web.Response:
        """
        Handle LOGIN action - initial authentication.

        Registers the console, generates tokens, and returns GameSpy info.

        Args:
            data: Form data dictionary
            client_ip: Client IP address

        Returns:
            Response with token, challenge, and locator
        """
        # Decode parameters
        userid = self._decode_param(data.get('userid', ''))
        macadr = self._format_mac_address(self._decode_param(data.get('macadr', '')))
        devname = self._decode_param(data.get('devname', 'Unknown'))
        gamecd = self._decode_param(data.get('gamecd', ''))

        logger.info(f"[NAS] Login: userid={userid}, mac={macadr}, device={devname}, game={gamecd}")

        # Register console in database
        try:
            await self._register_console(userid, macadr, devname, data)
        except Exception as e:
            logger.error(f"[NAS] Failed to register console: {e}")

        # Generate authentication tokens
        challenge = self._generate_challenge()
        token = self._generate_token(userid)

        # Log login attempt
        try:
            await self._log_nas_login(userid, client_ip, data, token, challenge)
        except Exception as e:
            logger.error(f"[NAS] Failed to log login: {e}")

        # Build response
        # Field order: locator, challenge, retry, token, returncd
        # NO datetime field - causes DS parsing failure
        response_data = {
            'locator': 'gamespy.com',
            'challenge': challenge,
            'retry': '0',
            'token': token,
            'returncd': '001'
        }

        response = self._build_nas_response(response_data)

        logger.info(f"[NAS] Login successful for {userid}")
        logger.debug(f"[NAS] Response: {response_data}")

        return response

    async def _handle_svcloc(self, data: dict, client_ip: str) -> web.Response:
        """
        Handle SVCLOC action - service location lookup.

        Returns hostnames for various Nintendo services (DLC, etc.).

        Args:
            data: Form data dictionary
            client_ip: Client IP address

        Returns:
            Response with service host and token
        """
        userid = self._decode_param(data.get('userid', ''))
        svc = self._decode_param(data.get('svc', ''))

        logger.info(f"[NAS] SVCLOC request from {userid} for service {svc}")

        authtoken = self._generate_token(userid)

        # Base response
        response = {
            'retry': '0',
            'returncd': '007',
            'statusdata': 'Y',
        }

        # Service-specific host configuration
        if svc in ('9000', '9001'):
            # DLC/Download Server
            response['svchost'] = 'dls1.nintendowifi.net'
            if svc == '9000':
                response['token'] = authtoken
            else:
                response['servicetoken'] = authtoken
        elif svc == '0000':
            # Pokemon special service
            response['servicetoken'] = authtoken
            response['svchost'] = 'n/a'
        else:
            # Unknown service
            response['svchost'] = 'n/a'
            response['servicetoken'] = authtoken

        response['datetime'] = datetime.utcnow().strftime('%Y%m%d%H%M%S')

        logger.debug(f"[NAS] SVCLOC response: {response}")

        return self._build_nas_response(response)

    async def _handle_acctcreate(self, data: dict, client_ip: str) -> web.Response:
        """
        Handle ACCTCREATE action - account creation.

        DS/Wii accounts are auto-created (no approval needed).

        Args:
            data: Form data dictionary
            client_ip: Client IP address

        Returns:
            Response with userid confirmation
        """
        userid = self._decode_param(data.get('userid', ''))
        macadr = self._format_mac_address(self._decode_param(data.get('macadr', '')))

        logger.info(f"[NAS] Account creation: userid={userid}, mac={macadr}")

        # Register console
        try:
            await self._register_console(userid, macadr, 'New User', data)
        except Exception as e:
            logger.error(f"[NAS] Failed to create account: {e}")

        return self._build_nas_response({
            'retry': '0',
            'returncd': '002',
            'userid': userid,
            'datetime': datetime.utcnow().strftime('%Y%m%d%H%M%S'),
        })

    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------

    async def _register_console(self, userid: str, macadr: str, devname: str, data: dict):
        """
        Register or update console via Django Admin API.

        Attempts to update existing console first, creates new if not found.

        Args:
            userid: Console user ID
            macadr: Formatted MAC address
            devname: Device name
            data: Original form data (for platform detection)
        """
        # Detect platform from device type
        platform = 'DS'
        devtype = data.get('devtype', '')
        if 'wii' in devtype.lower():
            platform = 'Wii'
        elif 'dsi' in devtype.lower():
            platform = 'DSi'

        console_data = {
            'mac_address': macadr,
            'user_id': userid,
            'device_name': devname,
            'platform': platform,
            'enabled': True,
        }

        async with ClientSession() as session:
            # Try to update existing console
            url = f"{self.api_url}/consoles/{macadr}/"
            try:
                async with session.patch(url, json=console_data,
                                        headers=self.api_headers,
                                        timeout=API_TIMEOUT) as resp:
                    if resp.status == 200:
                        logger.debug(f"[NAS] Console updated: {macadr}")
                        return
                    elif resp.status != 404:
                        error_text = await resp.text()
                        logger.warning(f"[NAS] API PATCH error: {resp.status} - {error_text}")
            except Exception as e:
                logger.debug(f"[NAS] PATCH failed: {e}")

            # Create new console
            url = f"{self.api_url}/consoles/"
            try:
                async with session.post(url, json=console_data,
                                       headers=self.api_headers,
                                       timeout=API_TIMEOUT) as resp:
                    if resp.status == 201:
                        logger.debug(f"[NAS] Console registered: {macadr}")
                    else:
                        error_text = await resp.text()
                        logger.warning(f"[NAS] Failed to register console: {resp.status} - {error_text}")
            except Exception as e:
                logger.error(f"[NAS] API POST error: {e}")

    async def _log_nas_login(self, userid: str, client_ip: str, data: dict,
                            token: str, challenge: str):
        """
        Log NAS login to Django Admin API.

        Stores the login for audit and for GP server to retrieve challenge.

        Args:
            userid: Console user ID
            client_ip: Client IP address
            data: Original form data
            token: Generated auth token
            challenge: Generated challenge
        """
        # Store challenge in data for GP server proof calculation
        data_with_challenge = data.copy()
        data_with_challenge['challenge'] = challenge

        login_data = {
            'user_id': userid,
            'auth_token': token,
            'ip_address': self._extract_client_ip(client_ip),
            'data': data_with_challenge,
        }

        async with ClientSession() as session:
            url = f"{self.api_url}/nas-logins/"
            try:
                async with session.post(url, json=login_data,
                                       headers=self.api_headers,
                                       timeout=API_TIMEOUT) as resp:
                    if resp.status == 201:
                        logger.debug(f"[NAS] Login logged for {userid}")
                    else:
                        error_text = await resp.text()
                        logger.warning(f"[NAS] Failed to log login: {resp.status} - {error_text}")
            except Exception as e:
                logger.error(f"[NAS] Failed to log login: {e}")

    # -------------------------------------------------------------------------
    # Server Lifecycle
    # -------------------------------------------------------------------------

    async def start(self):
        """Start NAS server and begin listening for connections."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        site = web.TCPSite(
            self.runner,
            self.config.NAS_HOST,
            self.config.NAS_PORT
        )
        await site.start()

        logger.info(
            f"NAS Server started on {self.config.NAS_HOST}:{self.config.NAS_PORT}"
        )

    async def stop(self):
        """Stop NAS server and cleanup resources."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("NAS Server stopped")


# -----------------------------------------------------------------------------
# Standalone Execution
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from dwc_server.config import config

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        server = NASServer(config)
        await server.start()

        print("\n" + "=" * 60)
        print("NAS Server Running")
        print("=" * 60)
        print(f"Listening on: http://{config.NAS_HOST}:{config.NAS_PORT}/ac")
        print(f"Health check: http://{config.NAS_HOST}:{config.NAS_PORT}/health")
        print("\nTest with:")
        print(f"  curl -X POST http://localhost:{config.NAS_PORT}/ac \\")
        print("    -d 'action=login&userid=123456&macadr=00:11:22:33:44:55'")
        print("\nPress Ctrl+C to stop")
        print("=" * 60 + "\n")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            await server.stop()

    asyncio.run(main())
