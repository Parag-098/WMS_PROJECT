"""
Django-Q tasks for background processing.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def process_bulk_import(file_path, model_type, user_id):
    """
    Process bulk import file in background.
    
    Args:
        file_path: Path to uploaded file
        model_type: Type of model (item, batch, order)
        user_id: ID of user who initiated import
    
    Returns:
        Dict with import results
    """
    import pandas as pd
    from django.contrib.auth import get_user_model
    from inventory.models import Item, Batch, Order, OrderItem
    from inventory.services.notifications_helper import notify
    
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
    }
    
    try:
        # Read file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        logger.info(f"Processing {len(df)} rows for {model_type}")
        
        # Process based on model type
        if model_type == "item":
            results = _process_item_import(df)
        elif model_type == "batch":
            results = _process_batch_import(df)
        elif model_type == "order":
            results = _process_order_import(df)
        
        # Notify user of completion
        notify(
            user=user,
            message=f"Import completed: {results['success']} rows imported, {results['failed']} failed",
            level="success" if results['failed'] == 0 else "warning",
            notification_type="import"
        )
        
        logger.info(f"Import task completed: {results}")
        
    except Exception as e:
        logger.error(f"Import task failed: {e}")
        notify(
            user=user,
            message=f"Import failed: {str(e)}",
            level="error",
            notification_type="import"
        )
        results["errors"].append(str(e))
    
    return results


def _process_item_import(df):
    """Process Item import."""
    from inventory.models import Item
    from django.db import transaction
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    for idx, row in df.iterrows():
        try:
            with transaction.atomic():
                sku = str(row.get("sku", "")).strip().upper()
                name = str(row.get("name", "")).strip()
                
                if not sku or not name:
                    raise ValueError("SKU and name are required")
                
                Item.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "name": name,
                        "description": str(row.get("description", "")),
                        "unit": str(row.get("unit", "pcs")),
                        "reorder_threshold": Decimal(str(row.get("reorder_threshold", 0))),
                    }
                )
                results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Row {idx+2}: {str(e)}")
    
    return results


def _process_batch_import(df):
    """Process Batch import."""
    import pandas as pd
    from inventory.models import Batch, Item
    from django.db import transaction
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    for idx, row in df.iterrows():
        try:
            with transaction.atomic():
                item_sku = str(row.get("item_sku", "")).strip().upper()
                lot_no = str(row.get("lot_no", "")).strip()
                
                if not item_sku or not lot_no:
                    raise ValueError("item_sku and lot_no are required")
                
                item = Item.objects.get(sku=item_sku)
                received_qty = Decimal(str(row.get("received_qty", 0)))
                
                Batch.objects.create(
                    item=item,
                    lot_no=lot_no,
                    received_qty=received_qty,
                    available_qty=received_qty,
                    expiry_date=pd.to_datetime(row.get("expiry_date")).date() if pd.notna(row.get("expiry_date")) else None,
                    status=Batch.STATUS_AVAILABLE,
                )
                results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Row {idx+2}: {str(e)}")
    
    return results


def _process_order_import(df):
    """Process Order import."""
    from inventory.models import Order, OrderItem, Item
    from django.db import transaction
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    # Group by order_no
    for order_no in df['order_no'].unique():
        try:
            with transaction.atomic():
                order_rows = df[df['order_no'] == order_no]
                first_row = order_rows.iloc[0]
                
                # Create order
                order = Order.objects.create(
                    order_no=str(first_row.get("order_no", "")).strip(),
                    customer_name=str(first_row.get("customer_name", "")).strip(),
                    status=Order.STATUS_PENDING,
                )
                
                # Create order items
                for _, row in order_rows.iterrows():
                    item_sku = str(row.get("item_sku", "")).strip().upper()
                    item = Item.objects.get(sku=item_sku)
                    
                    OrderItem.objects.create(
                        order=order,
                        item=item,
                        qty_requested=Decimal(str(row.get("qty_requested", 0))),
                        status=OrderItem.STATUS_PENDING,
                    )
                
                results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Order {order_no}: {str(e)}")
    
    return results


def scheduled_expiry_scan():
    """
    Daily scheduled task to scan for near-expiry and expired batches.
    Creates notifications for warehouse managers.
    
    Should be scheduled via Django-Q:
        from django_q.models import Schedule
        Schedule.objects.create(
            func='inventory.tasks.scheduled_expiry_scan',
            schedule_type='D',  # Daily
            name='Daily Expiry Scan',
        )
    """
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from inventory.models import Batch, Notification
    
    User = get_user_model()
    today = timezone.now().date()
    warning_threshold = today + timedelta(days=7)
    
    # Find expired batches
    expired = Batch.objects.filter(
        expiry_date__lt=today,
        status=Batch.STATUS_AVAILABLE,
        available_qty__gt=0
    ).select_related('item')
    
    # Find near-expiry batches
    near_expiry = Batch.objects.filter(
        expiry_date__gte=today,
        expiry_date__lte=warning_threshold,
        status=Batch.STATUS_AVAILABLE,
        available_qty__gt=0
    ).select_related('item')
    
    # Mark expired batches
    expired_count = 0
    for batch in expired:
        batch.status = Batch.STATUS_EXPIRED
        batch.save(update_fields=['status'])
        expired_count += 1
    
    # Create notifications for managers
    managers = User.objects.filter(is_staff=True)
    
    if expired_count > 0:
        for manager in managers:
            Notification.objects.create(
                user=manager,
                message=f"Expiry Scan: {expired_count} batch(es) have expired and been marked EXPIRED.",
                level=Notification.LEVEL_ERROR,
            )
    
    if near_expiry.exists():
        near_count = near_expiry.count()
        for manager in managers:
            Notification.objects.create(
                user=manager,
                message=f"Expiry Warning: {near_count} batch(es) will expire within 7 days.",
                level=Notification.LEVEL_WARNING,
            )
    
    logger.info(f"Expiry scan complete: {expired_count} expired, {near_expiry.count()} near expiry")
    
    return {
        "expired_count": expired_count,
        "near_expiry_count": near_expiry.count(),
    }


def generate_scheduled_report(report_type="inventory_snapshot"):
    """
    Generate scheduled reports for managers.
    
    Args:
        report_type: Type of report (inventory_snapshot, low_stock, transaction_summary)
    
    Should be scheduled via Django-Q for daily/weekly reports.
    """
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from inventory.models import Item, Batch, TransactionLog, Notification
    from django.db.models import Sum
    
    User = get_user_model()
    managers = User.objects.filter(is_staff=True)
    
    if report_type == "inventory_snapshot":
        # Count total items and batches
        item_count = Item.objects.count()
        batch_count = Batch.objects.filter(status=Batch.STATUS_AVAILABLE).count()
        total_qty = Batch.objects.filter(status=Batch.STATUS_AVAILABLE).aggregate(
            total=Sum('available_qty')
        )['total'] or 0
        
        message = (
            f"Daily Inventory Report:\n"
            f"- Total Items: {item_count}\n"
            f"- Active Batches: {batch_count}\n"
            f"- Total Available Qty: {total_qty}"
        )
        
    elif report_type == "low_stock":
        # Find items below reorder threshold
        low_stock_items = []
        for item in Item.objects.all():
            total = item.total_quantity()
            if item.reorder_threshold and total <= item.reorder_threshold:
                low_stock_items.append(f"{item.sku} ({total}/{item.reorder_threshold})")
        
        if low_stock_items:
            message = (
                f"Low Stock Alert ({len(low_stock_items)} items):\n" +
                "\n".join(f"- {item}" for item in low_stock_items[:10])
            )
            if len(low_stock_items) > 10:
                message += f"\n... and {len(low_stock_items) - 10} more"
        else:
            message = "Low Stock Report: All items are above reorder threshold."
    
    elif report_type == "transaction_summary":
        # Count transactions in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        txn_count = TransactionLog.objects.filter(timestamp__gte=yesterday).count()
        
        message = f"Transaction Summary (24h): {txn_count} transactions recorded."
    
    else:
        message = f"Unknown report type: {report_type}"
    
    # Create notifications for managers
    for manager in managers:
        Notification.objects.create(
            user=manager,
            message=message,
            level=Notification.LEVEL_INFO,
        )
    
    logger.info(f"Scheduled report generated: {report_type}")
    
    return {"report_type": report_type, "recipient_count": managers.count()}
