"""
URL configuration for DWC Server Admin Panel
"""

from django.contrib import admin
from django.urls import path, include
from dwc_admin import views

urlpatterns = [
    # Custom Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Django Admin
    path('admin/', admin.site.urls),
    
    # API
    path('api/', include('dwc_api.urls')),
]