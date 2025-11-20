"""
DRF API Views for DWC Server

This module provides REST API endpoints for managing:
- Consoles (Nintendo DS/Wii devices)
- Profiles (User profiles with friend codes)
- Sessions (GP server sessions)
- NAS Logins (Authentication logs)
- Bans (Banned items)
- Game Servers (QR server registrations)
- Statistics (Server statistics)
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from dwc_admin.database_manager import DatabaseManager
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

from .serializers import (
    BannedItemSerializer,
    ConsoleSerializer,
    GameServerSerializer,
    NASLoginSerializer,
    NatNegSerializer,
    PendingSerializer,
    ProfileListSerializer,
    ProfileSerializer,
    ServerStatisticSerializer,
    SessionSerializer,
    StatsOverviewSerializer,
)


# =============================================================================
# Constants
# =============================================================================

# Timeout constants (in minutes)
ONLINE_TIMEOUT_MINUTES = 5      # Console/server considered online
RECENT_TIMEOUT_MINUTES = 60     # Console considered recently active
SESSION_TIMEOUT_MINUTES = 30    # Session considered active
HEARTBEAT_TIMEOUT_MINUTES = 2   # Game server heartbeat timeout


# =============================================================================
# Console ViewSet
# =============================================================================

class ConsoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing consoles.

    Actions:
    - list: Get all consoles
    - retrieve: Get specific console by MAC address
    - create: Register new console
    - update: Update console info
    - partial_update: Partially update console
    - destroy: Delete console
    - online: Get only online consoles
    - enable: Enable a console
    - disable: Disable a console
    """

    queryset = Console.objects.all()
    serializer_class = ConsoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'enabled']
    search_fields = ['mac_address', 'user_id', 'device_name']
    ordering_fields = ['registered_at', 'last_seen']
    ordering = ['-last_seen']
    lookup_field = 'mac_address'

    def get_permissions(self):
        """Allow public access for create (registration) and list."""
        if self.action in ['create', 'list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def online(self, request):
        """Get only online consoles (active in last 5 minutes)."""
        cutoff = timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
        consoles = self.queryset.filter(last_seen__gte=cutoff)
        serializer = self.get_serializer(consoles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def enable(self, request, mac_address=None):
        """Enable a console."""
        console = self.get_object()
        console.enabled = True
        console.save()
        return Response({'status': 'console enabled'})

    @action(detail=True, methods=['post'])
    def disable(self, request, mac_address=None):
        """Disable a console."""
        console = self.get_object()
        console.enabled = False
        console.save()
        return Response({'status': 'console disabled'})


# =============================================================================
# Profile ViewSet
# =============================================================================

class ProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing profiles.

    Actions:
    - list: Get all profiles
    - retrieve: Get specific profile by ID
    - create: Create new profile
    - update: Update profile
    - destroy: Delete profile
    - by_game: Get profiles for a specific game
    - lookup_friend_code: Find profile by friend code
    """

    queryset = Profile.objects.select_related('console').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['game_id', 'enabled', 'user_id']
    search_fields = ['profile_id', 'user_id', 'uniquenick']
    ordering_fields = ['created_at', 'profile_id']
    ordering = ['-created_at']

    def get_permissions(self):
        """Allow public access for create, list, retrieve, update, partial_update, and lookup."""
        if self.action in ['create', 'list', 'retrieve', 'update', 'partial_update',
                          'by_game', 'lookup_friend_code']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Use lighter serializer for list view."""
        if self.action == 'list':
            return ProfileListSerializer
        return ProfileSerializer

    @action(detail=False, methods=['get'])
    def by_game(self, request):
        """Get profiles for a specific game."""
        game_id = request.query_params.get('game_id')
        if not game_id:
            return Response(
                {'error': 'game_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        profiles = self.queryset.filter(game_id=game_id)
        serializer = self.get_serializer(profiles, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def lookup_friend_code(self, request):
        """
        Lookup profile by friend code.

        Note: This is not efficient for large datasets but works for now.
        Consider adding a friend_code field to the model for better performance.
        """
        fc = request.query_params.get('friend_code')
        if not fc:
            return Response(
                {'error': 'friend_code parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Remove dashes for comparison
        fc_clean = fc.replace('-', '')

        # Search through profiles
        for profile in self.queryset:
            if profile.friend_code.replace('-', '') == fc_clean:
                serializer = ProfileSerializer(profile)
                return Response(serializer.data)

        return Response(
            {'error': 'Profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# =============================================================================
# Session ViewSet
# =============================================================================

class SessionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing GameSpy GP sessions.

    Actions:
    - list: Get all sessions
    - retrieve: Get session by session_key
    - create: Create new session (auto-generates session_key)
    - destroy: Delete session (logout)
    - active: Get only active sessions
    - get_profile: Get profile associated with session
    - cleanup: Remove old sessions
    """

    queryset = Session.objects.select_related('profile').all()
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['profile']
    ordering_fields = ['login_time']
    ordering = ['-login_time']
    lookup_field = 'session_key'

    def get_permissions(self):
        """Allow public access for create, retrieve, destroy, get_profile, and cleanup."""
        if self.action in ['create', 'retrieve', 'destroy', 'get_profile', 'cleanup']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Create new session - generates session_key automatically."""
        profile_id = request.data.get('profile_id')

        if not profile_id:
            return Response(
                {'error': 'profile_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session_key = DatabaseManager.create_session(profile_id)
            session = Session.objects.get(session_key=session_key)
            serializer = self.get_serializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Profile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active sessions (within last 30 minutes)."""
        cutoff = timezone.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        sessions = self.queryset.filter(login_time__gte=cutoff)
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def get_profile(self, request, session_key=None):
        """Get profile associated with session."""
        session = self.get_object()
        profile_serializer = ProfileSerializer(session.profile)
        return Response(profile_serializer.data)

    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Cleanup old sessions."""
        max_age = int(request.data.get('max_age_minutes', SESSION_TIMEOUT_MINUTES))
        deleted = DatabaseManager.cleanup_old_sessions(max_age)
        return Response({'deleted': deleted})


# =============================================================================
# NAS Login ViewSet
# =============================================================================

class NASLoginViewSet(viewsets.ModelViewSet):
    """
    API endpoint for viewing NAS logins.

    Actions:
    - list: Get all NAS logins
    - retrieve: Get specific login
    - create: Create new login record
    - recent: Get logins from last hour
    """

    queryset = NASLogin.objects.all()
    serializer_class = NASLoginSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user_id', 'ip_address', 'auth_token']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_permissions(self):
        """Allow public access for create and list (for GameSpy server)."""
        if self.action in ['create', 'list']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get logins from last hour."""
        cutoff = timezone.now() - timedelta(minutes=RECENT_TIMEOUT_MINUTES)
        logins = self.queryset.filter(timestamp__gte=cutoff)
        serializer = self.get_serializer(logins, many=True)
        return Response(serializer.data)


# =============================================================================
# Banned Item ViewSet
# =============================================================================

class BannedItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing bans.

    Actions:
    - list: Get all bans
    - retrieve: Get specific ban
    - create: Create new ban
    - update: Update ban
    - destroy: Remove ban
    - active: Get only active bans
    - check: Check if an identifier is banned
    """

    queryset = BannedItem.objects.all()
    serializer_class = BannedItemSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['ban_type']
    search_fields = ['identifier', 'reason']

    def get_permissions(self):
        """Allow public access for check endpoint (needed by GameSpy server)."""
        if self.action == 'check':
            return [AllowAny()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active bans."""
        now = timezone.now()
        bans = self.queryset.filter(
            expires_at__gt=now
        ) | self.queryset.filter(expires_at__isnull=True)
        serializer = self.get_serializer(bans, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def check(self, request):
        """Check if an identifier is banned."""
        ban_type = request.data.get('ban_type')
        identifier = request.data.get('identifier')

        if not ban_type or not identifier:
            return Response(
                {'error': 'ban_type and identifier required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ban = self.queryset.get(ban_type=ban_type, identifier=identifier)
            if ban.is_active():
                return Response({
                    'banned': True,
                    'reason': ban.reason,
                    'expires_at': ban.expires_at,
                })
            else:
                return Response({'banned': False})
        except BannedItem.DoesNotExist:
            return Response({'banned': False})


# =============================================================================
# Game Server ViewSet
# =============================================================================

class GameServerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for game servers.

    Actions:
    - list: Get all game servers
    - retrieve: Get specific server
    - create: Register new server
    - update: Update server info
    - destroy: Unregister server
    - online: Get only online servers
    - by_game: Get servers for a specific game
    - heartbeat: Update server heartbeat
    """

    queryset = GameServer.objects.select_related(
        'host_profile',
        'host_profile__console'
    ).all()
    serializer_class = GameServerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['game_name']
    search_fields = ['server_id', 'game_name', 'ip_address']
    ordering = ['-last_heartbeat']
    lookup_field = 'server_id'
    lookup_value_regex = '[a-zA-Z0-9]+'

    def get_permissions(self):
        """Allow public access for list, retrieve, online, by_game, heartbeat, create, and update."""
        if self.action in ['list', 'retrieve', 'online', 'by_game', 'heartbeat',
                          'create', 'update', 'partial_update']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def online(self, request):
        """Get only online servers (heartbeat in last 2 minutes)."""
        cutoff = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        servers = self.queryset.filter(last_heartbeat__gte=cutoff)
        serializer = self.get_serializer(servers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_game(self, request):
        """Get servers for a specific game."""
        game_name = request.query_params.get('game_name')
        if not game_name:
            return Response(
                {'error': 'game_name parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        servers = self.queryset.filter(game_name=game_name)
        serializer = self.get_serializer(servers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def heartbeat(self, request, server_id=None):
        """Update server heartbeat."""
        server = self.get_object()

        # Update player count if provided
        current_players = request.data.get('current_players')
        if current_players is not None:
            server.current_players = current_players

        server.save(update_fields=['last_heartbeat', 'current_players'])

        return Response({'status': 'heartbeat received'})


# =============================================================================
# Server Statistic ViewSet
# =============================================================================

class ServerStatisticViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for server statistics (read-only).

    Actions:
    - list: Get all statistics
    - retrieve: Get specific statistic
    - latest: Get latest statistics
    - history: Get statistics history
    """

    queryset = ServerStatistic.objects.all()
    serializer_class = ServerStatisticSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-timestamp']

    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest statistics."""
        try:
            latest = self.queryset.latest('timestamp')
            serializer = self.get_serializer(latest)
            return Response(serializer.data)
        except ServerStatistic.DoesNotExist:
            return Response(
                {'error': 'No statistics available'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get statistics history."""
        days = int(request.query_params.get('days', 7))
        cutoff = timezone.now() - timedelta(days=days)

        stats = self.queryset.filter(timestamp__gte=cutoff)
        serializer = self.get_serializer(stats, many=True)
        return Response(serializer.data)


# =============================================================================
# Standalone API Views
# =============================================================================

@api_view(['GET'])
def stats_overview(request):
    """
    Get overview statistics (Public endpoint).

    Returns current server statistics including:
    - Total counts (consoles, profiles, bans)
    - Online counts (consoles, servers)
    - Recent activity (logins)
    - Platform distribution
    - Top games
    """
    now = timezone.now()
    online_cutoff = now - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
    recent_cutoff = now - timedelta(minutes=RECENT_TIMEOUT_MINUTES)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    stats = {
        'total_consoles': Console.objects.count(),
        'total_profiles': Profile.objects.count(),
        'total_bans': BannedItem.objects.filter(
            expires_at__gt=now
        ).count() + BannedItem.objects.filter(expires_at__isnull=True).count(),
        'online_consoles': Console.objects.filter(last_seen__gte=online_cutoff).count(),
        'online_servers': GameServer.objects.filter(last_heartbeat__gte=online_cutoff).count(),
        'recent_logins': NASLogin.objects.filter(timestamp__gte=recent_cutoff).count(),
        'logins_today': NASLogin.objects.filter(timestamp__gte=today_start).count(),
        'consoles_by_platform': list(
            Console.objects.values('platform').annotate(count=Count('mac_address'))
        ),
        'top_games': list(
            Profile.objects.values('game_id').annotate(
                count=Count('profile_id')
            ).order_by('-count')[:5]
        ),
    }

    serializer = StatsOverviewSerializer(stats)
    return Response(serializer.data)


@api_view(['GET'])
def api_root(request):
    """
    API Root - List all available endpoints.

    Returns a dictionary of available API endpoints and documentation link.
    """
    return Response({
        'endpoints': {
            'stats': '/api/stats/',
            'consoles': '/api/consoles/',
            'profiles': '/api/profiles/',
            'sessions': '/api/sessions/',
            'nas_logins': '/api/nas-logins/',
            'bans': '/api/bans/',
            'game_servers': '/api/game-servers/',
            'statistics': '/api/statistics/',
        },
        'documentation': '/api/docs/',
    })
