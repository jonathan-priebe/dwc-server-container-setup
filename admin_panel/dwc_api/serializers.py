"""
DRF Serializers for DWC Server API

This module provides serializers for all DWC models, handling:
- Data validation
- Nested relationships
- Computed fields (status, friend_code, etc.)
- Read-only fields
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from dwc_admin.models import (
    BannedItem,
    Console,
    GameServer,
    NASLogin,
    NatNeg,
    Pending,
    Profile,
    ServerStatistic,
    Session,
)


# =============================================================================
# Constants
# =============================================================================

# Status timeout thresholds (in minutes)
ONLINE_TIMEOUT_MINUTES = 5
RECENT_TIMEOUT_MINUTES = 60


# =============================================================================
# Console Serializers
# =============================================================================

class ConsoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Console model.

    Includes computed fields:
    - status: online/recent/offline based on last_seen
    - profile_count: number of profiles for this console
    """

    status = serializers.SerializerMethodField()
    profile_count = serializers.SerializerMethodField()

    class Meta:
        model = Console
        fields = [
            'mac_address',
            'user_id',
            'device_name',
            'platform',
            'enabled',
            'registered_at',
            'last_seen',
            'status',
            'profile_count',
        ]
        read_only_fields = ['registered_at', 'last_seen']

    def get_status(self, obj):
        """
        Get online status based on last_seen timestamp.

        Returns:
            str: 'online' if active in last 5 minutes,
                 'recent' if active in last hour,
                 'offline' otherwise
        """
        now = timezone.now()
        if obj.last_seen > now - timedelta(minutes=ONLINE_TIMEOUT_MINUTES):
            return 'online'
        elif obj.last_seen > now - timedelta(minutes=RECENT_TIMEOUT_MINUTES):
            return 'recent'
        return 'offline'

    def get_profile_count(self, obj):
        """Get number of profiles for this console."""
        return obj.profiles.count()


# =============================================================================
# Profile Serializers
# =============================================================================

class ProfileSerializer(serializers.ModelSerializer):
    """
    Full serializer for Profile model.

    Includes:
    - friend_code: Computed friend code
    - console_info: Nested console information
    """

    friend_code = serializers.ReadOnlyField()
    console_info = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'profile_id',
            'user_id',
            'game_id',
            'console',
            'console_info',
            'friend_code',
            'enabled',
            'created_at',
            'gs_broadcast_code',
            'uniquenick',
            'firstname',
            'lastname',
        ]
        read_only_fields = ['profile_id', 'created_at', 'friend_code']

    def get_console_info(self, obj):
        """
        Get basic console info for this profile.

        Returns:
            dict or None: Console details if available
        """
        if obj.console:
            return {
                'mac_address': obj.console.mac_address,
                'device_name': obj.console.device_name,
                'platform': obj.console.platform,
            }
        return None


class ProfileListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for Profile list views.

    Excludes console_info for better performance on large lists.
    """

    friend_code = serializers.ReadOnlyField()

    class Meta:
        model = Profile
        fields = [
            'profile_id',
            'user_id',
            'game_id',
            'friend_code',
            'enabled',
            'created_at',
            'uniquenick',
        ]


# =============================================================================
# Session Serializer
# =============================================================================

class SessionSerializer(serializers.ModelSerializer):
    """
    Serializer for Session model.

    Includes:
    - profile_info: Basic profile information
    - is_active: Whether session is still active
    """

    profile_info = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            'session_key',
            'profile',
            'profile_info',
            'login_time',
            'is_active',
        ]
        read_only_fields = ['session_key', 'login_time']

    def get_profile_info(self, obj):
        """Get basic profile info for this session."""
        return {
            'profile_id': obj.profile.profile_id,
            'user_id': obj.profile.user_id,
            'game_id': obj.profile.game_id,
        }

    def get_is_active(self, obj):
        """Check if session is still active."""
        return obj.is_active()


# =============================================================================
# NAS Login Serializer
# =============================================================================

class NASLoginSerializer(serializers.ModelSerializer):
    """Serializer for NASLogin model."""

    class Meta:
        model = NASLogin
        fields = [
            'id',
            'user_id',
            'auth_token',
            'data',
            'timestamp',
            'ip_address',
        ]
        read_only_fields = ['id', 'timestamp']


# =============================================================================
# Banned Item Serializer
# =============================================================================

class BannedItemSerializer(serializers.ModelSerializer):
    """
    Serializer for BannedItem model.

    Includes:
    - is_active: Whether ban is currently active
    - ban_type_display: Human-readable ban type
    """

    is_active = serializers.SerializerMethodField()
    ban_type_display = serializers.CharField(source='get_ban_type_display', read_only=True)

    class Meta:
        model = BannedItem
        fields = [
            'id',
            'ban_type',
            'ban_type_display',
            'identifier',
            'reason',
            'banned_at',
            'expires_at',
            'banned_by',
            'is_active',
        ]
        read_only_fields = ['id', 'banned_at']

    def get_is_active(self, obj):
        """Check if ban is still active."""
        return obj.is_active()


# =============================================================================
# Game Server Serializer
# =============================================================================

class GameServerSerializer(serializers.ModelSerializer):
    """
    Serializer for GameServer model.

    Includes:
    - host_profile_info: Information about the host profile
    - is_online: Whether server is currently online
    - address: Formatted IP:port string
    """

    host_profile_info = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = GameServer
        fields = [
            'id',
            'server_id',
            'game_name',
            'host_profile',
            'host_profile_info',
            'address',
            'ip_address',
            'port',
            'max_players',
            'current_players',
            'game_data',
            'registered_at',
            'last_heartbeat',
            'is_online',
        ]
        read_only_fields = ['id', 'registered_at', 'last_heartbeat']

    def get_host_profile_info(self, obj):
        """
        Get host profile information.

        Returns:
            dict or None: Profile details if available
        """
        if not obj.host_profile:
            return None
        return {
            'profile_id': obj.host_profile.profile_id,
            'friend_code': obj.host_profile.friend_code,
            'console_name': (
                obj.host_profile.console.device_name
                if obj.host_profile.console else None
            ),
        }

    def get_is_online(self, obj):
        """Check if server is currently online."""
        return obj.is_online()

    def get_address(self, obj):
        """Get formatted address string."""
        return f"{obj.ip_address}:{obj.port}"


# =============================================================================
# Server Statistic Serializer
# =============================================================================

class ServerStatisticSerializer(serializers.ModelSerializer):
    """Serializer for ServerStatistic model."""

    class Meta:
        model = ServerStatistic
        fields = [
            'id',
            'timestamp',
            'active_consoles',
            'active_profiles',
            'active_servers',
            'total_logins_today',
        ]
        read_only_fields = ['id', 'timestamp']


# =============================================================================
# Matchmaking Serializers
# =============================================================================

class PendingSerializer(serializers.ModelSerializer):
    """
    Serializer for Pending matchmaking model.

    Includes profile_info for context.
    """

    profile_info = serializers.SerializerMethodField()

    class Meta:
        model = Pending
        fields = [
            'id',
            'profile',
            'profile_info',
            'group_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_profile_info(self, obj):
        """Get basic profile info."""
        return {
            'profile_id': obj.profile.profile_id,
            'user_id': obj.profile.user_id,
        }


class NatNegSerializer(serializers.ModelSerializer):
    """Serializer for NAT negotiation model."""

    class Meta:
        model = NatNeg
        fields = [
            'cookie',
            'client_addr',
            'client_port',
            'created_at',
        ]
        read_only_fields = ['created_at']


# =============================================================================
# Statistics Overview Serializer
# =============================================================================

class StatsOverviewSerializer(serializers.Serializer):
    """
    Serializer for overall server statistics.

    This is a non-model serializer for the stats_overview endpoint.
    """

    total_consoles = serializers.IntegerField()
    total_profiles = serializers.IntegerField()
    total_bans = serializers.IntegerField()
    online_consoles = serializers.IntegerField()
    online_servers = serializers.IntegerField()
    recent_logins = serializers.IntegerField()
    logins_today = serializers.IntegerField()
    consoles_by_platform = serializers.ListField()
    top_games = serializers.ListField()
