"""
Custom Dashboard Views for DWC Server Admin
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from dwc_admin.models import Console, Profile, NASLogin, GameServer, ServerStatistic


@staff_member_required
def dashboard_view(request):
    """Custom dashboard with statistics"""
 
    # Current stats
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)
    one_hour_ago = now - timedelta(hours=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 🔑 Calculate total_consoles first to resolve the NameError
    total_consoles_count = Console.objects.count()

    stats = {
        # Totals
        'total_consoles': total_consoles_count, # Use the pre-calculated count
        'total_profiles': Profile.objects.count(),
        'total_bans': Console.objects.filter(enabled=False).count(),
        
        # Active (last 5 minutes)
        'online_consoles': Console.objects.filter(
            last_seen__gte=five_min_ago
        ).count(),
        'online_servers': GameServer.objects.filter(
            last_heartbeat__gte=five_min_ago
        ).count(),
        
        # Recent activity (last hour)
        'recent_logins': NASLogin.objects.filter(
            timestamp__gte=one_hour_ago
        ).count(),
        
        # Today
        'logins_today': NASLogin.objects.filter(
            timestamp__gte=today_start
        ).count(),
        
        # By platform
        'consoles_by_platform': [
            {
                'platform': item['platform'],
                'count': item['count'],
                # 👇 Use total_consoles_count instead of stats['total_consoles']
                'percentage': round(item['count'] * 100 / total_consoles_count, 1) if total_consoles_count > 0 else 0
            }
            for item in Console.objects.values('platform').annotate(count=Count('mac_address'))
        ],
        
        # ... rest of the dictionary definition ...
        'top_games': Profile.objects.values('game_id').annotate(
            count=Count('profile_id')
        ).order_by('-count')[:5],
        
        # Recent consoles
        'recent_consoles': Console.objects.order_by('-last_seen')[:5],
        
        # Active game servers
        'active_servers': GameServer.objects.filter(
            last_heartbeat__gte=five_min_ago
        ).select_related('host_profile', 'host_profile__console'),
        
        # Recent NAS logins
        'recent_nas_logins': NASLogin.objects.order_by('-timestamp')[:10],
    }
    
    # ... (rest of the function is unchanged)
    # Get statistics history (last 7 days)
    stats_history = ServerStatistic.objects.order_by('-timestamp')[:7]
    
    context = {
        'stats': stats,
        'stats_history': stats_history,
        'now': now,
    }
    
    return render(request, 'admin/dashboard.html', context)