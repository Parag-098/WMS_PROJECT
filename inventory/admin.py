from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Item,
    Batch,
    Order,
    OrderItem,
    Allocation,
    Shipment,
    TransactionLog,
    Notification,
    UndoStack,
    RedoStack,
    GraphNode,
    GraphEdge,
    Return,
)


# =============================
# Import/Export Resources
# =============================

class ItemResource(resources.ModelResource):
    class Meta:
        model = Item
        import_id_fields = ["sku"]
        fields = ("sku", "name", "description", "unit", "reorder_threshold")


class BatchResource(resources.ModelResource):
    class Meta:
        model = Batch
        import_id_fields = ["item", "lot_no"]
        fields = ("item__sku", "lot_no", "received_qty", "available_qty", "expiry_date", "status")


class OrderResource(resources.ModelResource):
    class Meta:
        model = Order
        import_id_fields = ["order_no"]
        fields = ("order_no", "customer_name", "status", "created_at")


# =============================
# Admin Classes
# =============================

@admin.register(Item)
class ItemAdmin(ImportExportModelAdmin):
    resource_class = ItemResource
    list_display = ["sku", "name", "unit", "reorder_threshold", "get_total_quantity"]
    list_filter = ["unit"]
    search_fields = ["sku", "name", "description"]
    ordering = ["sku"]

    def get_total_quantity(self, obj):
        return obj.total_quantity()
    get_total_quantity.short_description = "Total Available"


@admin.register(Batch)
class BatchAdmin(ImportExportModelAdmin):
    resource_class = BatchResource
    list_display = ["lot_no", "item", "received_qty", "available_qty", "expiry_date", "status"]
    list_filter = ["status", "expiry_date"]
    search_fields = ["lot_no", "item__sku", "item__name"]
    ordering = ["item__sku", "lot_no"]
    raw_id_fields = ["item"]


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    resource_class = OrderResource
    list_display = ["order_no", "customer_name", "status", "created_at", "get_is_fully_allocated"]
    list_filter = ["status", "created_at"]
    search_fields = ["order_no", "customer_name"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    def get_is_fully_allocated(self, obj):
        return obj.is_fully_allocated
    get_is_fully_allocated.short_description = "Fully Allocated"
    get_is_fully_allocated.boolean = True


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "item", "qty_requested", "qty_allocated"]
    list_filter = ["order__status"]
    search_fields = ["order__order_no", "item__sku", "item__name"]
    raw_id_fields = ["order", "item"]
    ordering = ["-order__created_at"]


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ["order_item", "batch", "qty_allocated", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["order_item__order__order_no", "order_item__item__sku", "batch__lot_no"]
    raw_id_fields = ["order_item", "batch"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ["shipment_no", "order", "tracking_no", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["shipment_no", "order__order_no", "tracking_no"]
    raw_id_fields = ["order"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    readonly_fields = ["tracking_no"]


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ["type", "qty", "item", "batch", "order", "shipment", "user", "timestamp"]
    list_filter = ["type", "timestamp"]
    search_fields = ["item__sku", "batch__lot_no", "order__order_no", "shipment__shipment_no", "user__username"]
    raw_id_fields = ["user", "item", "batch", "order", "shipment"]
    ordering = ["-timestamp"]
    date_hierarchy = "timestamp"
    readonly_fields = ["user", "type", "qty", "item", "batch", "order", "shipment", "timestamp", "meta"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["message_preview", "level", "user", "is_read", "created_at"]
    list_filter = ["level", "is_read", "created_at"]
    search_fields = ["message", "user__username"]
    raw_id_fields = ["user"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    actions = ["mark_as_read", "mark_as_unread"]

    def message_preview(self, obj):
        return obj.message[:60] + "..." if len(obj.message) > 60 else obj.message
    message_preview.short_description = "Message"

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Mark selected as unread"


@admin.register(UndoStack)
class UndoStackAdmin(admin.ModelAdmin):
    list_display = ["op_name", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["op_name"]
    ordering = ["-created_at", "-id"]
    readonly_fields = ["op_name", "metadata", "created_at"]


@admin.register(RedoStack)
class RedoStackAdmin(admin.ModelAdmin):
    list_display = ["op_name", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["op_name"]
    ordering = ["-created_at", "-id"]
    readonly_fields = ["op_name", "metadata", "created_at"]


@admin.register(GraphNode)
class GraphNodeAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "group", "pos_x", "pos_y"]
    list_filter = ["group"]
    search_fields = ["key", "label"]
    ordering = ["key"]


@admin.register(GraphEdge)
class GraphEdgeAdmin(admin.ModelAdmin):
    list_display = ["source", "target", "label", "weight", "directed"]
    list_filter = ["directed"]
    search_fields = ["source__key", "target__key", "label"]
    raw_id_fields = ["source", "target"]
    ordering = ["source__key", "target__key"]


@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ["return_no", "order_item", "qty_returned", "reason", "status", "created_at"]
    list_filter = ["status", "reason", "created_at"]
    search_fields = ["return_no", "order_item__order__order_no", "order_item__item__sku"]
    readonly_fields = ["return_no", "created_at", "processed_at"]
    raw_id_fields = ["order_item"]
    ordering = ["-created_at"]
