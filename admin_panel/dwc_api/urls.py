"""
URL configuration for DWC API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'consoles', views.ConsoleViewSet, basename='console')
router.register(r'profiles', views.ProfileViewSet, basename='profile')
router.register(r'sessions', views.SessionViewSet, basename='session')
router.register(r'nas-logins', views.NASLoginViewSet, basename='naslogin')
router.register(r'bans', views.BannedItemViewSet, basename='ban')
router.register(r'game-servers', views.GameServerViewSet, basename='gameserver')
router.register(r'statistics', views.ServerStatisticViewSet, basename='statistic')

urlpatterns = [
    # API root
    path('', views.api_root, name='api-root'),
    
    # Stats overview
    path('stats/', views.stats_overview, name='stats-overview'),
    
    # Router URLs
    path('', include(router.urls)),
]