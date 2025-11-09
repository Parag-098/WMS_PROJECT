from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    
    # Item URLs
    path("items/", views.ItemListView.as_view(), name="item-list"),
    path("items/", views.ItemListView.as_view(), name="item-list-alt"),
    path("items/create/", views.ItemCreateView.as_view(), name="item-create"),
    path("items/<slug:sku>/", views.ItemDetailView.as_view(), name="item-detail"),
    path("items/<slug:sku>/update/", views.ItemUpdateView.as_view(), name="item-update"),
    path("items/<slug:sku>/delete/", views.ItemDeleteView.as_view(), name="item-delete"),
    
    # Batch URLs
    path("batches/", views.BatchListView.as_view(), name="batch-list"),
    path("batches/create/", views.BatchCreateView.as_view(), name="batch-create"),
    path("batches/<int:pk>/", views.BatchDetailView.as_view(), name="batch-detail"),
    path("batches/<int:pk>/update/", views.BatchUpdateView.as_view(), name="batch-update"),
    path("batches/<int:pk>/delete/", views.BatchDeleteView.as_view(), name="batch-delete"),
    
    # Receive URL
    path("receive/", views.ReceiveView.as_view(), name="receive"),
    
    # Order URLs
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/create/", views.OrderCreateView.as_view(), name="order-create"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/update/", views.OrderUpdateView.as_view(), name="order-update"),
    path("orders/<int:pk>/cancel/", views.OrderCancelView.as_view(), name="order-cancel"),
    path("orders/<int:pk>/delete/", views.OrderDeleteView.as_view(), name="order-delete"),
    
    # Order allocation
    path("order/<int:order_id>/allocate/", views.AllocateOrderView.as_view(), name="order-allocate"),
    path("order/<int:order_id>/deallocate/", views.DeallocateOrderView.as_view(), name="order-deallocate"),
    
    # Pick, Pack, Ship URLs
    path("order/<int:order_id>/pick/", views.PickView.as_view(), name="order-pick"),
    path("order/<int:order_id>/pack/", views.PackView.as_view(), name="order-pack"),
    path("order/<int:order_id>/ship/", views.ShipView.as_view(), name="order-ship"),
    path("order/<int:order_id>/deliver/", views.DeliverView.as_view(), name="order-deliver"),
    
    # RMA (Return) URLs
    path("returns/", views.ReturnListView.as_view(), name="return-list"),
    path("returns/create/", views.CreateReturnView.as_view(), name="return-create"),
    path("returns/<int:pk>/", views.ReturnDetailView.as_view(), name="return-detail"),
    path("returns/<int:return_id>/process/", views.ProcessReturnView.as_view(), name="return-process"),
    
    # Undo/Redo URLs
    path("undo/", views.UndoView.as_view(), name="undo"),
    path("redo/", views.RedoView.as_view(), name="redo"),
    path("undo-redo-history/", views.UndoRedoHistoryView.as_view(), name="undo-redo-history"),
    
    # Notification URLs
    path("notifications/unread/", views.UnreadNotificationsView.as_view(), name="notifications-unread"),
    path("notifications/<int:notification_id>/read/", views.MarkNotificationReadView.as_view(), name="notification-read"),
    path("notifications/read-all/", views.MarkAllNotificationsReadView.as_view(), name="notifications-read-all"),
    
    # Webhook endpoint
    path("webhook/", views.WebhookReceiverView.as_view(), name="webhook-receiver"),
    
    # Bulk Import URLs
    path("import/", views.BulkImportView.as_view(), name="bulk_import"),
    path("import/commit/", views.BulkImportCommitView.as_view(), name="bulk_import_commit"),
    
    # Export routes
    path("export/", views.ExportMenuView.as_view(), name="export_menu"),
    path("export/inventory-snapshot/", views.ExportInventorySnapshotView.as_view(), name="export_inventory_snapshot"),
    path("export/batches/", views.ExportBatchesView.as_view(), name="export_batches"),
    path("export/transaction-log/", views.ExportTransactionLogView.as_view(), name="export_transaction_log"),
    path("export/orders-allocations/", views.ExportOrdersAllocationsView.as_view(), name="export_orders_allocations"),

    # Graph views
    path("graph/", views.GraphView.as_view(), name="graph"),
    path("graph/data/", views.GraphDataView.as_view(), name="graph_data"),

    # Stock Overview
    path("stock-overview/", views.StockOverviewView.as_view(), name="stock-overview"),
    path("api/stock-overview/", views.StockOverviewDataView.as_view(), name="stock-overview-data"),

    # Warehouse Management Features
    path("low-stock-alert/", views.LowStockAlertView.as_view(), name="low-stock-alert"),
    path("expiry-tracking/", views.ExpiryTrackingView.as_view(), name="expiry-tracking"),
    path("movement-report/", views.InventoryMovementReportView.as_view(), name="movement-report"),
    
    # Search Features with Excel Export
    path("lot-search/", views.LotSearchView.as_view(), name="lot-search"),
    path("item-search/", views.ItemSearchView.as_view(), name="item-search"),
    path("customer-search/", views.CustomerSearchView.as_view(), name="customer-search"),
    path("export/lot-report/", views.ExportLotReportView.as_view(), name="export-lot-report"),
    path("export/lot-report.csv", views.ExportLotReportCSVView.as_view(), name="export-lot-report-csv"),
    path("export/item-report/", views.ExportItemReportView.as_view(), name="export-item-report"),
    path("export/item-report.csv", views.ExportItemReportCSVView.as_view(), name="export-item-report-csv"),
    path("export/customer-report/", views.ExportCustomerReportView.as_view(), name="export-customer-report"),
    path("export/customer-report.csv", views.ExportCustomerReportCSVView.as_view(), name="export-customer-report-csv"),

    # Batch Order Processor (Queue + Stack)
    path("batch-processor/", views.BatchProcessorView.as_view(), name="batch-processor"),
    path("batch-processor/trace/", views.BatchProcessorTraceView.as_view(), name="batch-processor-trace"),

    # Sandbox (Stack/Queue)
    path("sandbox/stack/", views.SandboxStackView.as_view(), name="sandbox_stack"),
    path("sandbox/queue/", views.SandboxQueueView.as_view(), name="sandbox_queue"),
    path("sandbox/apply/", views.ApplySandboxOperationsView.as_view(), name="sandbox_apply"),
]
