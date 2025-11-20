"""
Django Admin configuration for DWC Server
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from .models import (
    Console, Profile, Session, NASLogin,
    AllowList, DenyList, BannedItem, GameServer, Pending, NatNeg, ServerStatistic
)


@admin.register(Console)
class ConsoleAdmin(admin.ModelAdmin):
    list_display = [
        'device_name_display',
        'mac_address',
        'platform',
        'enabled_display',
        'last_seen_display'
    ]
    list_filter = ['platform', 'enabled', 'registered_at']
    search_fields = ['mac_address', 'user_id', 'device_name']
    readonly_fields = ['registered_at', 'last_seen']
    actions = ['enable_consoles', 'disable_consoles']
    
    fieldsets = (
        ('Console Information', {
            'fields': ('mac_address', 'user_id', 'device_name', 'platform')
        }),
        ('Status', {
            'fields': ('enabled', 'registered_at', 'last_seen')
        }),
    )
    
    def device_name_display(self, obj):
        return obj.device_name or '[Unnamed]'
    device_name_display.short_description = 'Device Name'
    
    def enabled_display(self, obj):
        if obj.enabled:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    enabled_display.short_description = 'Status'
    
    def last_seen_display(self, obj):
        now = timezone.now()
        diff = now - obj.last_seen
        
        if diff < timedelta(minutes=5):
            color = 'green'
            status = 'Online'
        elif diff < timedelta(hours=1):
            color = 'orange'
            status = f'{int(diff.total_seconds() / 60)}m ago'
        else:
            color = 'gray'
            status = obj.last_seen.strftime('%Y-%m-%d %H:%M')
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color, status
        )
    last_seen_display.short_description = 'Last Seen'
    
    def enable_consoles(self, request, queryset):
        count = queryset.update(enabled=True)
        self.message_user(request, f'{count} console(s) enabled.')
    enable_consoles.short_description = "✓ Enable selected consoles"
    
    def disable_consoles(self, request, queryset):
        count = queryset.update(enabled=False)
        self.message_user(request, f'{count} console(s) disabled.')
    disable_consoles.short_description = "✗ Disable selected consoles"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'profile_id',
        'user_id',
        'game_id',
        'friend_code_display',
        'uniquenick',
        'enabled_display'
    ]
    list_filter = ['game_id', 'enabled', 'created_at']
    search_fields = ['profile_id', 'user_id', 'uniquenick', 'game_id', 'email']
    readonly_fields = ['profile_id', 'created_at', 'friend_code_display', 'cfc']

    fieldsets = (
        ('Profile Information', {
            'fields': ('profile_id', 'user_id', 'game_id', 'console')
        }),
        ('Friend Code', {
            'fields': ('friend_code_display', 'cfc'),
            'description': 'Friend code is automatically calculated and cached'
        }),
        ('Authentication', {
            'fields': ('password', 'email'),
            'classes': ('collapse',)
        }),
        ('GameSpy Data', {
            'fields': ('gs_broadcast_code', 'uniquenick', 'pid'),
            'classes': ('collapse',)
        }),
        ('Personal Information', {
            'fields': ('firstname', 'lastname', 'birth'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('lon', 'lat', 'loc', 'zipcode'),
            'classes': ('collapse',)
        }),
        ('Console/Device Info', {
            'fields': ('csnum', 'bssid', 'devname', 'aim'),
            'classes': ('collapse',)
        }),
        ('Stats & Status', {
            'fields': ('stat', 'partnerid', 'enabled', 'created_at')
        }),
    )
    
    def friend_code_display(self, obj):
        fc = obj.friend_code
        return format_html(
            '<strong style="font-family: monospace; font-size: 16px; color: #0066cc;">{}</strong>',
            fc
        )
    friend_code_display.short_description = 'Friend Code'
    
    def enabled_display(self, obj):
        if obj.enabled:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    enabled_display.short_description = 'Enabled'


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_key_short',
        'profile',
        'login_time',
        'is_active_display'
    ]
    list_filter = ['login_time']
    search_fields = ['session_key', 'profile__user_id', 'profile__profile_id']
    readonly_fields = ['session_key', 'profile', 'login_time']

    def session_key_short(self, obj):
        return obj.session_key[:16] + '...'
    session_key_short.short_description = 'Session Key'

    def is_active_display(self, obj):
        if obj.is_active():
            return format_html('<span style="color: green;">● Active</span>')
        return format_html('<span style="color: gray;">○ Expired</span>')
    is_active_display.short_description = 'Status'

    def has_add_permission(self, request):
        # Sessions are created via GP login
        return False


@admin.register(Pending)
class PendingAdmin(admin.ModelAdmin):
    list_display = ['profile', 'group_id', 'created_at']
    list_filter = ['group_id', 'created_at']
    search_fields = ['profile__user_id', 'profile__profile_id']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        # Pending entries are created by matchmaking
        return False


@admin.register(NatNeg)
class NatNegAdmin(admin.ModelAdmin):
    list_display = ['cookie', 'client_addr', 'client_port', 'created_at']
    list_filter = ['created_at']
    search_fields = ['cookie', 'client_addr']
    readonly_fields = ['created_at']

    def has_add_permission(self, request):
        # NAT negotiation entries are created by natneg server
        return False


@admin.register(NASLogin)
class NASLoginAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'ip_address', 'timestamp_display']
    list_filter = ['timestamp']
    search_fields = ['user_id', 'ip_address', 'auth_token']
    readonly_fields = ['timestamp', 'data']
    date_hierarchy = 'timestamp'

    def timestamp_display(self, obj):
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    timestamp_display.short_description = 'Timestamp'

    def has_add_permission(self, request):
        # Don't allow manual creation
        return False


@admin.register(AllowList)
class AllowListAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'mac_address', 'enabled', 'added_at']
    list_filter = ['enabled', 'added_at']
    search_fields = ['user_id', 'mac_address', 'notes']
    readonly_fields = ['added_at']
    actions = ['enable_entries', 'disable_entries']

    fieldsets = (
        ('Whitelist Entry', {
            'fields': ('user_id', 'mac_address', 'enabled')
        }),
        ('Details', {
            'fields': ('notes', 'added_at')
        }),
    )

    def enable_entries(self, request, queryset):
        count = queryset.update(enabled=True)
        self.message_user(request, f'{count} whitelist entry(ies) enabled.')
    enable_entries.short_description = "✓ Enable selected entries"

    def disable_entries(self, request, queryset):
        count = queryset.update(enabled=False)
        self.message_user(request, f'{count} whitelist entry(ies) disabled.')
    disable_entries.short_description = "✗ Disable selected entries"


@admin.register(DenyList)
class DenyListAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'game_id', 'reason_short', 'banned_at', 'banned_by']
    list_filter = ['game_id', 'banned_at']
    search_fields = ['user_id', 'game_id', 'reason', 'banned_by']
    readonly_fields = ['banned_at']

    fieldsets = (
        ('Ban Information', {
            'fields': ('user_id', 'game_id', 'reason')
        }),
        ('Metadata', {
            'fields': ('banned_by', 'banned_at')
        }),
    )

    def reason_short(self, obj):
        if len(obj.reason) > 50:
            return obj.reason[:50] + '...'
        return obj.reason or '[No reason]'
    reason_short.short_description = 'Reason'


@admin.register(BannedItem)
class BannedItemAdmin(admin.ModelAdmin):
    list_display = [
        'ban_type',
        'identifier',
        'reason_short',
        'banned_at',
        'expires_at',
        'is_active_display'
    ]
    list_filter = ['ban_type', 'banned_at']
    search_fields = ['identifier', 'reason']
    readonly_fields = ['banned_at']
    
    fieldsets = (
        ('Ban Information', {
            'fields': ('ban_type', 'identifier', 'reason')
        }),
        ('Duration', {
            'fields': ('banned_at', 'expires_at'),
            'description': 'Leave "Expires at" empty for permanent ban'
        }),
        ('Metadata', {
            'fields': ('banned_by',)
        }),
    )
    
    def reason_short(self, obj):
        if len(obj.reason) > 50:
            return obj.reason[:50] + '...'
        return obj.reason or '[No reason]'
    reason_short.short_description = 'Reason'
    
    def is_active_display(self, obj):
        if obj.is_active():
            return format_html('<span style="color: red; font-weight: bold;">⛔ BANNED</span>')
        return format_html('<span style="color: green;">✓ Expired</span>')
    is_active_display.short_description = 'Status'


@admin.register(GameServer)
class GameServerAdmin(admin.ModelAdmin):
    list_display = [
        'server_id',
        'game_name',
        'host_profile',
        'address_display',
        'players_display',
        'is_online_display',
        'last_heartbeat'
    ]
    list_filter = ['game_name', 'last_heartbeat']
    search_fields = ['server_id', 'game_name', 'ip_address']
    readonly_fields = ['registered_at', 'last_heartbeat']
    
    def address_display(self, obj):
        return f"{obj.ip_address}:{obj.port}"
    address_display.short_description = 'Address'
    
    def players_display(self, obj):
        return f"{obj.current_players}/{obj.max_players}"
    players_display.short_description = 'Players'
    
    def is_online_display(self, obj):
        if obj.is_online():
            return format_html('<span style="color: green;">● Online</span>')
        return format_html('<span style="color: gray;">○ Offline</span>')
    is_online_display.short_description = 'Status'
    
    def has_add_permission(self, request):
        # Servers are registered via QR protocol
        return False


@admin.register(ServerStatistic)
class ServerStatisticAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'active_consoles',
        'active_profiles',
        'active_servers',
        'total_logins_today'
    ]
    readonly_fields = ['timestamp']
    
    def has_add_permission(self, request):
        # Statistics are auto-generated
        return False
    
    def has_change_permission(self, request, obj=None):
        # Statistics are read-only
        return False


# Customize Admin Site
admin.site.site_header = "DWC Server Administration"
admin.site.site_title = "DWC Server Admin"
admin.site.index_title = "Nintendo Wi-Fi Connection Server Management"