"""
Database Manager for DWC Server - Django ORM version

This is a Django-based implementation of the GameSpy database layer,
equivalent to gs_database.py but using Django ORM instead of raw SQLite.

Based on: jonathan-priebe/dwc_network_server_emulator

Provides methods for:
- Profile management (create, update, lookup)
- Session management (login/logout)
- NAS login tracking
- Matchmaking queue (pending)
- NAT negotiation
- Game server registration
- Ban management (whitelist, denylist, generic bans)
- Console management
"""

import secrets
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from .friendcode import format_friend_code, generate_friend_code
from .models import (
    AllowList,
    BannedItem,
    Console,
    DenyList,
    GameServer,
    NASLogin,
    NatNeg,
    Pending,
    Profile,
    Session,
)


# =============================================================================
# Constants
# =============================================================================

# Timeout constants (in minutes)
SESSION_TIMEOUT_MINUTES = 30
HEARTBEAT_TIMEOUT_MINUTES = 2


# =============================================================================
# Database Manager
# =============================================================================

class DatabaseManager:
    """
    Django ORM-based database manager for GameSpy operations.

    This class provides methods similar to the original gs_database.py
    but uses Django's ORM for better integration with the admin panel.

    All methods are static for easy use without instantiation.
    """

    # =========================================================================
    # Profile Management
    # =========================================================================

    @staticmethod
    def get_profile_by_id(profile_id: int) -> Optional[Profile]:
        """
        Get profile by profile ID.

        Args:
            profile_id: The profile ID to look up

        Returns:
            Profile object or None if not found
        """
        try:
            return Profile.objects.get(profile_id=profile_id)
        except Profile.DoesNotExist:
            return None

    @staticmethod
    def get_profile_by_uniquenick(uniquenick: str) -> Optional[Profile]:
        """
        Get profile by unique nickname.

        Args:
            uniquenick: The unique nickname to look up

        Returns:
            Profile object or None if not found
        """
        try:
            return Profile.objects.get(uniquenick=uniquenick)
        except Profile.DoesNotExist:
            return None

    @staticmethod
    def get_or_create_profile(user_id: str, game_id: str, **kwargs) -> Profile:
        """
        Get existing profile or create new one for user+game combo.

        This is the main entry point for profile creation during login.
        If a profile exists, it returns it. Otherwise, creates a new one
        with friend code generation.

        Args:
            user_id: Nintendo User ID
            game_id: Game ID (e.g., 'ADAJ' for Pokemon Diamond)
            **kwargs: Additional profile fields to set

        Returns:
            Profile object (existing or newly created)
        """
        with transaction.atomic():
            profile, created = Profile.objects.get_or_create(
                user_id=user_id,
                game_id=game_id,
                defaults=kwargs
            )

            if created:
                # Generate and cache friend code
                fc = generate_friend_code(profile.profile_id, game_id)
                profile.cfc = format_friend_code(fc)
                profile.save(update_fields=['cfc'])

            return profile

    @staticmethod
    def create_profile(user_id: str, game_id: str, **kwargs) -> Profile:
        """
        Force create a new profile (will fail if user_id+game_id exists).

        Args:
            user_id: Nintendo User ID
            game_id: Game ID
            **kwargs: Additional profile fields

        Returns:
            Newly created Profile object

        Raises:
            IntegrityError: If profile already exists
        """
        profile = Profile.objects.create(
            user_id=user_id,
            game_id=game_id,
            **kwargs
        )

        # Generate and cache friend code
        fc = generate_friend_code(profile.profile_id, game_id)
        profile.cfc = format_friend_code(fc)
        profile.save(update_fields=['cfc'])

        return profile

    @staticmethod
    def update_profile(profile_id: int, **kwargs) -> bool:
        """
        Update profile fields.

        Args:
            profile_id: Profile ID to update
            **kwargs: Fields to update

        Returns:
            True if profile was updated, False if not found
        """
        updated = Profile.objects.filter(profile_id=profile_id).update(**kwargs)
        return updated > 0

    # =========================================================================
    # Session Management
    # =========================================================================

    @staticmethod
    def generate_session_key() -> str:
        """
        Generate a secure random session key.

        Returns:
            Random hex string (32 characters)
        """
        return secrets.token_hex(16)

    @staticmethod
    def create_session(profile_id: int) -> str:
        """
        Create a new GameSpy GP session.

        Args:
            profile_id: Profile ID to create session for

        Returns:
            Session key string

        Raises:
            Profile.DoesNotExist: If profile doesn't exist
        """
        profile = Profile.objects.get(profile_id=profile_id)
        session_key = DatabaseManager.generate_session_key()

        Session.objects.create(
            session_key=session_key,
            profile=profile
        )

        return session_key

    @staticmethod
    def get_session(session_key: str) -> Optional[Session]:
        """
        Get session by session key.

        Args:
            session_key: Session key to look up

        Returns:
            Session object or None if not found
        """
        try:
            return Session.objects.select_related('profile').get(session_key=session_key)
        except Session.DoesNotExist:
            return None

    @staticmethod
    def get_profile_from_session(session_key: str) -> Optional[Profile]:
        """
        Get profile associated with a session key.

        Args:
            session_key: Session key to look up

        Returns:
            Profile object or None if session not found
        """
        session = DatabaseManager.get_session(session_key)
        return session.profile if session else None

    @staticmethod
    def delete_session(session_key: str) -> bool:
        """
        Delete a session (logout).

        Args:
            session_key: Session key to delete

        Returns:
            True if session was deleted, False if not found
        """
        deleted, _ = Session.objects.filter(session_key=session_key).delete()
        return deleted > 0

    @staticmethod
    def cleanup_old_sessions(max_age_minutes: int = SESSION_TIMEOUT_MINUTES) -> int:
        """
        Delete sessions older than max_age_minutes.

        Args:
            max_age_minutes: Maximum session age in minutes (default: 30)

        Returns:
            Number of sessions deleted
        """
        threshold = timezone.now() - timedelta(minutes=max_age_minutes)
        deleted, _ = Session.objects.filter(login_time__lt=threshold).delete()
        return deleted

    # =========================================================================
    # NAS Login Management
    # =========================================================================

    @staticmethod
    def create_nas_login(user_id: str, auth_token: str, data: dict, ip_address: str) -> NASLogin:
        """
        Record a NAS authentication.

        Args:
            user_id: Nintendo User ID
            auth_token: Authentication token
            data: Complete NAS login data (will be stored as JSON)
            ip_address: Client IP address

        Returns:
            NASLogin object
        """
        return NASLogin.objects.create(
            user_id=user_id,
            auth_token=auth_token,
            data=data,
            ip_address=ip_address
        )

    @staticmethod
    def get_nas_login_by_token(auth_token: str) -> Optional[NASLogin]:
        """
        Get NAS login by auth token.

        Args:
            auth_token: Authentication token to look up

        Returns:
            NASLogin object or None if not found
        """
        try:
            return NASLogin.objects.get(auth_token=auth_token)
        except NASLogin.DoesNotExist:
            return None

    # =========================================================================
    # Matchmaking / Pending
    # =========================================================================

    @staticmethod
    def add_to_pending(profile_id: int, group_id: int) -> Pending:
        """
        Add profile to matchmaking queue.

        Args:
            profile_id: Profile ID to add
            group_id: Matchmaking group ID

        Returns:
            Pending object
        """
        profile = Profile.objects.get(profile_id=profile_id)
        pending, _ = Pending.objects.get_or_create(
            profile=profile,
            group_id=group_id
        )
        return pending

    @staticmethod
    def remove_from_pending(profile_id: int, group_id: int) -> bool:
        """
        Remove profile from matchmaking queue.

        Args:
            profile_id: Profile ID to remove
            group_id: Matchmaking group ID

        Returns:
            True if removed, False if not found
        """
        deleted, _ = Pending.objects.filter(
            profile__profile_id=profile_id,
            group_id=group_id
        ).delete()
        return deleted > 0

    @staticmethod
    def get_pending_profiles(group_id: int) -> List[Profile]:
        """
        Get all profiles in a matchmaking group.

        Args:
            group_id: Matchmaking group ID

        Returns:
            List of Profile objects
        """
        pending = Pending.objects.filter(group_id=group_id).select_related('profile')
        return [p.profile for p in pending]

    # =========================================================================
    # NAT Negotiation
    # =========================================================================

    @staticmethod
    def create_natneg(cookie: int, client_addr: str, client_port: int) -> NatNeg:
        """
        Create NAT negotiation entry.

        Args:
            cookie: NAT negotiation cookie
            client_addr: Client IP address
            client_port: Client port

        Returns:
            NatNeg object
        """
        natneg, _ = NatNeg.objects.update_or_create(
            cookie=cookie,
            defaults={
                'client_addr': client_addr,
                'client_port': client_port
            }
        )
        return natneg

    @staticmethod
    def get_natneg(cookie: int) -> Optional[NatNeg]:
        """
        Get NAT negotiation by cookie.

        Args:
            cookie: NAT negotiation cookie

        Returns:
            NatNeg object or None if not found
        """
        try:
            return NatNeg.objects.get(cookie=cookie)
        except NatNeg.DoesNotExist:
            return None

    @staticmethod
    def delete_natneg(cookie: int) -> bool:
        """
        Delete NAT negotiation entry.

        Args:
            cookie: NAT negotiation cookie

        Returns:
            True if deleted, False if not found
        """
        deleted, _ = NatNeg.objects.filter(cookie=cookie).delete()
        return deleted > 0

    # =========================================================================
    # Game Server Management
    # =========================================================================

    @staticmethod
    def register_game_server(server_id: str, game_name: str, profile_id: int,
                             ip_address: str, port: int, **kwargs) -> GameServer:
        """
        Register a game server.

        Args:
            server_id: Unique server identifier
            game_name: Game name
            profile_id: Host profile ID
            ip_address: Server IP
            port: Server port
            **kwargs: Additional server data

        Returns:
            GameServer object
        """
        profile = Profile.objects.get(profile_id=profile_id)

        server, _ = GameServer.objects.update_or_create(
            server_id=server_id,
            defaults={
                'game_name': game_name,
                'host_profile': profile,
                'ip_address': ip_address,
                'port': port,
                **kwargs
            }
        )
        return server

    @staticmethod
    def get_game_servers(game_name: Optional[str] = None) -> List[GameServer]:
        """
        Get active game servers.

        Args:
            game_name: Optional filter by game name

        Returns:
            List of GameServer objects with heartbeat within last 2 minutes
        """
        threshold = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)

        qs = GameServer.objects.filter(last_heartbeat__gt=threshold)
        if game_name:
            qs = qs.filter(game_name=game_name)

        return list(qs)

    # =========================================================================
    # Whitelist (AllowList) Management
    # =========================================================================

    @staticmethod
    def is_whitelisted(user_id: int, mac_address: str) -> bool:
        """
        Check if a user/MAC is in the whitelist.

        Args:
            user_id: User ID to check
            mac_address: MAC address to check

        Returns:
            True if whitelisted and enabled, False otherwise
        """
        try:
            entry = AllowList.objects.get(user_id=user_id)
            return entry.enabled and entry.mac_address == mac_address
        except AllowList.DoesNotExist:
            return False

    @staticmethod
    def add_to_whitelist(user_id: int, mac_address: str, notes: str = "") -> AllowList:
        """
        Add user/MAC to whitelist.

        Args:
            user_id: User ID
            mac_address: MAC address
            notes: Optional admin notes

        Returns:
            AllowList object
        """
        entry, _ = AllowList.objects.update_or_create(
            user_id=user_id,
            defaults={
                'mac_address': mac_address,
                'enabled': True,
                'notes': notes
            }
        )
        return entry

    @staticmethod
    def remove_from_whitelist(user_id: int) -> bool:
        """
        Remove user from whitelist.

        Args:
            user_id: User ID to remove

        Returns:
            True if removed, False if not found
        """
        deleted, _ = AllowList.objects.filter(user_id=user_id).delete()
        return deleted > 0

    # =========================================================================
    # Deny List (Game-Specific Bans)
    # =========================================================================

    @staticmethod
    def is_denied(user_id: int, game_id: str) -> bool:
        """
        Check if a user is banned from a specific game.

        Args:
            user_id: User ID to check
            game_id: Game ID to check

        Returns:
            True if banned, False otherwise
        """
        return DenyList.objects.filter(user_id=user_id, game_id=game_id).exists()

    @staticmethod
    def add_to_denylist(user_id: int, game_id: str, reason: str = "",
                        banned_by: str = "") -> DenyList:
        """
        Ban a user from a specific game.

        Args:
            user_id: User ID to ban
            game_id: Game ID to ban from
            reason: Reason for ban
            banned_by: Who issued the ban

        Returns:
            DenyList object
        """
        entry, _ = DenyList.objects.update_or_create(
            user_id=user_id,
            game_id=game_id,
            defaults={
                'reason': reason,
                'banned_by': banned_by
            }
        )
        return entry

    @staticmethod
    def remove_from_denylist(user_id: int, game_id: str) -> bool:
        """
        Unban a user from a specific game.

        Args:
            user_id: User ID to unban
            game_id: Game ID to unban from

        Returns:
            True if removed, False if not found
        """
        deleted, _ = DenyList.objects.filter(user_id=user_id, game_id=game_id).delete()
        return deleted > 0

    # =========================================================================
    # Ban Management (Generic)
    # =========================================================================

    @staticmethod
    def is_banned(ban_type: str, identifier: str) -> bool:
        """
        Check if an identifier is banned.

        Args:
            ban_type: Type of ban ('ip', 'mac', 'profile', 'userid')
            identifier: The identifier to check

        Returns:
            True if banned and active, False otherwise
        """
        try:
            ban = BannedItem.objects.get(ban_type=ban_type, identifier=identifier)
            return ban.is_active()
        except BannedItem.DoesNotExist:
            return False

    @staticmethod
    def add_ban(ban_type: str, identifier: str, reason: str = "",
                expires_at=None, banned_by: str = "") -> BannedItem:
        """
        Add a ban.

        Args:
            ban_type: Type of ban ('ip', 'mac', 'profile', 'userid')
            identifier: The identifier to ban
            reason: Reason for ban
            expires_at: Expiration datetime (None = permanent)
            banned_by: Who issued the ban

        Returns:
            BannedItem object
        """
        ban, _ = BannedItem.objects.update_or_create(
            ban_type=ban_type,
            identifier=identifier,
            defaults={
                'reason': reason,
                'expires_at': expires_at,
                'banned_by': banned_by
            }
        )
        return ban

    @staticmethod
    def remove_ban(ban_type: str, identifier: str) -> bool:
        """
        Remove a ban.

        Args:
            ban_type: Type of ban
            identifier: The identifier to unban

        Returns:
            True if removed, False if not found
        """
        deleted, _ = BannedItem.objects.filter(
            ban_type=ban_type,
            identifier=identifier
        ).delete()
        return deleted > 0

    # =========================================================================
    # Console Management
    # =========================================================================

    @staticmethod
    def get_or_create_console(mac_address: str, **kwargs) -> Console:
        """
        Get or create console by MAC address.

        Args:
            mac_address: Console MAC address
            **kwargs: Additional console fields

        Returns:
            Console object
        """
        console, created = Console.objects.get_or_create(
            mac_address=mac_address,
            defaults=kwargs
        )

        if not created:
            # Update last_seen
            console.last_seen = timezone.now()
            console.save(update_fields=['last_seen'])

        return console

    @staticmethod
    def is_console_enabled(mac_address: str) -> bool:
        """
        Check if console is enabled (whitelist check).

        Args:
            mac_address: Console MAC address

        Returns:
            True if console exists and is enabled, False otherwise
        """
        try:
            console = Console.objects.get(mac_address=mac_address)
            return console.enabled
        except Console.DoesNotExist:
            # If console doesn't exist, assume not allowed
            return False
