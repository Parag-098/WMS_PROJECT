"""
DRF API ViewSets for WMS.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token

from .models import Order, Item, Shipment
from .serializers import (
    OrderSerializer,
    ItemSerializer,
    ShipmentSerializer,
    ShipmentStatusUpdateSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Orders.
    
    - list: List all orders
    - create: Create new order with items
    - retrieve: Get order detail
    - update/partial_update: Update order
    - destroy: Delete order
    """
    
    queryset = Order.objects.prefetch_related('items__item').all()
    serializer_class = OrderSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_no'
    
    def get_queryset(self):
        """Allow filtering by status."""
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class ItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Items (read-only).
    
    - list: List all items with current quantity
    - retrieve: Get item detail
    """
    
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_field = 'sku'
    
    def get_queryset(self):
        """Allow search by SKU or name."""
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(sku__icontains=search) | qs.filter(name__icontains=search)
        return qs


class ShipmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Shipments.
    
    - list: List all shipments
    - create: Create new shipment
    - retrieve: Get shipment detail
    - update_status: Custom action to update status only
    """
    
    queryset = Shipment.objects.select_related('order').all()
    serializer_class = ShipmentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_field = 'shipment_no'
    
    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, shipment_no=None):
        """
        Custom endpoint to update shipment status.
        
        POST /api/shipments/{shipment_no}/update-status/
        Body: {"status": "in_transit"}
        """
        shipment = self.get_object()
        serializer = ShipmentStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            new_status = serializer.validated_data['status']
            shipment.status = new_status
            shipment.save(update_fields=['status'])
            
            return Response({
                'shipment_no': shipment.shipment_no,
                'status': shipment.status,
                'message': f'Status updated to {shipment.get_status_display()}'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomObtainAuthToken(ObtainAuthToken):
    """
    Custom token authentication endpoint.
    
    POST /api/token/
    Body: {"username": "...", "password": "..."}
    Response: {"token": "...", "user_id": ..., "username": "..."}
    """
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'email': user.email,
        })
