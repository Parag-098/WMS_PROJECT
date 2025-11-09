"""
DRF serializers for WMS API.
"""
from rest_framework import serializers
from decimal import Decimal
from .models import Order, OrderItem, Item, Shipment, Batch


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for Item with current available quantity."""
    
    current_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = Item
        fields = ['id', 'sku', 'name', 'description', 'unit', 'reorder_threshold', 'current_qty']
        read_only_fields = ['id']
    
    def get_current_qty(self, obj):
        """Return total available quantity across all batches."""
        return float(obj.total_quantity())


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem."""
    
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'item', 'item_sku', 'item_name', 'qty_requested', 'qty_allocated']
        read_only_fields = ['id', 'qty_allocated']


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items inline."""
    
    item_sku = serializers.CharField(max_length=64)
    qty_requested = serializers.DecimalField(max_digits=12, decimal_places=3)
    
    def validate_qty_requested(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate_item_sku(self, value):
        if not Item.objects.filter(sku=value.upper().strip()).exists():
            raise serializers.ValidationError(f"Item with SKU '{value}' does not exist")
        return value.upper().strip()


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order with nested items."""
    
    items = OrderItemSerializer(many=True, read_only=True)
    items_data = OrderItemCreateSerializer(many=True, write_only=True, required=False)
    is_fully_allocated = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_no', 'customer_name', 'status', 'created_at', 'items', 'items_data', 'is_fully_allocated']
        read_only_fields = ['id', 'created_at', 'status']
    
    def create(self, validated_data):
        """Create order with items."""
        from django.db import transaction
        
        items_data = validated_data.pop('items_data', [])
        
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            
            for item_data in items_data:
                item = Item.objects.get(sku=item_data['item_sku'])
                OrderItem.objects.create(
                    order=order,
                    item=item,
                    qty_requested=item_data['qty_requested'],
                )
            
            return order


class ShipmentSerializer(serializers.ModelSerializer):
    """Serializer for Shipment."""
    
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    
    class Meta:
        model = Shipment
        fields = ['id', 'shipment_no', 'order', 'order_no', 'tracking_no', 'status', 'created_at']
        read_only_fields = ['id', 'tracking_no', 'created_at']


class ShipmentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating shipment status."""
    
    status = serializers.ChoiceField(choices=Shipment.STATUS_CHOICES)
