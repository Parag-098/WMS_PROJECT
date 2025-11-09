"""
Notification and webhook utilities for inventory events.
"""
import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


# =============================
# Email Notifications
# =============================

def send_shipment_notification(shipment, recipient_email=None):
    """
    Send shipment notification email (console backend).
    
    Args:
        shipment: Shipment instance
        recipient_email: Optional recipient email (defaults to order customer email if available)
    """
    subject = f"Shipment Confirmation - Order {shipment.order.order_no}"
    
    context = {
        "shipment": shipment,
        "order": shipment.order,
        "tracking_no": shipment.tracking_no,
        "carrier": shipment.carrier,
    }
    
    # Render plain text message
    message = f"""
Dear {shipment.order.customer_name},

Your order {shipment.order.order_no} has been shipped!

Tracking Number: {shipment.tracking_no}
Carrier: {shipment.carrier or 'N/A'}
Shipped On: {shipment.shipped_at.strftime('%Y-%m-%d %H:%M')}

Shipping Address:
{shipment.shipping_address}

Thank you for your business!
    """.strip()
    
    # Use console email backend (outputs to console)
    recipient = recipient_email or "customer@example.com"
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info(f"Shipment notification sent for {shipment.tracking_no} to {recipient}")
    except Exception as e:
        logger.error(f"Failed to send shipment notification: {e}")


def send_low_stock_alert(item, current_qty):
    """
    Send low stock alert email to inventory managers.
    
    Args:
        item: Item instance
        current_qty: Current total quantity
    """
    subject = f"Low Stock Alert - {item.sku}"
    
    message = f"""
INVENTORY ALERT

Item: {item.sku} - {item.name}
Current Quantity: {current_qty} {item.unit}
Reorder Threshold: {item.reorder_threshold} {item.unit}

Action Required: Please review inventory levels and reorder as needed.
    """.strip()
    
    managers = getattr(settings, "INVENTORY_MANAGER_EMAILS", ["manager@example.com"])
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=managers,
            fail_silently=False,
        )
        logger.info(f"Low stock alert sent for {item.sku}")
    except Exception as e:
        logger.error(f"Failed to send low stock alert: {e}")


# =============================
# Webhook Triggers
# =============================

def trigger_webhook(event_type, payload):
    """
    Trigger external webhook for inventory events.
    
    Args:
        event_type: Event type string (e.g., "shipment.created", "order.fulfilled")
        payload: Dict containing event data
    """
    webhook_url = getattr(settings, "INVENTORY_WEBHOOK_URL", None)
    
    if not webhook_url:
        logger.debug(f"No webhook URL configured for event: {event_type}")
        return
    
    webhook_data = {
        "event": event_type,
        "timestamp": payload.get("timestamp"),
        "data": payload,
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        logger.info(f"Webhook triggered for {event_type}: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook failed for {event_type}: {e}")


def webhook_shipment_created(shipment):
    """Trigger webhook when shipment is created."""
    payload = {
        "timestamp": shipment.shipped_at.isoformat(),
        "shipment_id": shipment.id,
        "tracking_no": shipment.tracking_no,
        "order_no": shipment.order.order_no,
        "customer_name": shipment.order.customer_name,
        "carrier": shipment.carrier,
    }
    trigger_webhook("shipment.created", payload)


def webhook_order_fulfilled(order):
    """Trigger webhook when order is fully fulfilled."""
    from django.utils import timezone
    payload = {
        "timestamp": timezone.now().isoformat(),
        "order_id": order.id,
        "order_no": order.order_no,
        "customer_name": order.customer_name,
        "status": order.status,
    }
    trigger_webhook("order.fulfilled", payload)


def webhook_inventory_adjusted(batch, old_qty, new_qty, reason):
    """Trigger webhook when inventory is manually adjusted."""
    from django.utils import timezone
    payload = {
        "timestamp": timezone.now().isoformat(),
        "batch_id": batch.id,
        "item_sku": batch.item.sku,
        "lot_no": batch.lot_no,
        "old_quantity": str(old_qty),
        "new_quantity": str(new_qty),
        "reason": reason,
    }
    trigger_webhook("inventory.adjusted", payload)
