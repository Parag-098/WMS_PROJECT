"""
API URL routing for DRF endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import (
    OrderViewSet,
    ItemViewSet,
    ShipmentViewSet,
    CustomObtainAuthToken,
)

# DRF router for viewsets
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'shipments', ShipmentViewSet, basename='shipment')

app_name = 'api'

urlpatterns = [
    # Token authentication endpoint
    path('token/', CustomObtainAuthToken.as_view(), name='token'),
    
    # ViewSet routes
    path('', include(router.urls)),
]
