from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # API endpoints removed for commercial version
    # path('api/', include('inventory.api_urls')),
    path('', include('inventory.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
