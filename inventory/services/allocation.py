"""
Allocation service for order fulfillment.

Implements order assignment using a manual FIFO queue and manual LIFO stack (no inbuilt queue/deque).
The stack is used to traverse available batches deterministically; the queue drives order item tasks.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from inventory.models import (
    Order,
    OrderItem,
    Batch,
    Allocation,
    TransactionLog,
    Notification,
)


class AllocationError(Exception):
    """Base exception for allocation errors."""
    pass


class OrderNotFoundError(AllocationError):
    """Raised when order does not exist."""
    pass


class InsufficientStockError(AllocationError):
    """Raised when there is insufficient stock to fulfill an order item."""
    pass


def allocate_order(order_id: int, user=None) -> Dict[str, Any]:
    """
    Allocate inventory for an order using manual Queue (FIFO) + Stack (LIFO).

    - Queue drives order item tasks in FIFO (received order lines processed in order).
    - For each item, eligible batches are pushed to a manual Stack such that pop() yields
      the next batch to consume (we push in reverse FEFO so the stack returns earliest expiry first).
    - This demonstrates explicit data-structure usage instead of relying on Python built-ins.
    """
    try:
        order = Order.objects.select_related().get(pk=order_id)
    except Order.DoesNotExist:
        raise OrderNotFoundError(f"Order with ID {order_id} not found")

    if order.status == Order.STATUS_CANCELLED:
        raise AllocationError(f"Cannot allocate cancelled order {order.order_no}")

    order_items = list(order.items.select_related("item").all())
    if not order_items:
        raise AllocationError(f"Order {order.order_no} has no items")

    from .structures import ManualQueue, ManualStack
    from django.utils import timezone

    allocation_results: List[Dict[str, Any]] = []
    items_fully_allocated = 0
    items_partially_allocated = 0
    items_failed = 0

    # Build a task queue of order items needing allocation
    task_q: ManualQueue[OrderItem] = ManualQueue(max(16, len(order_items)))
    for oi in order_items:
        task_q.enqueue(oi)

    with transaction.atomic():
        while not task_q.is_empty():
            order_item = task_q.dequeue()
            result = _allocate_item_with_stack(order_item, user)
            allocation_results.append(result)

            if result["status"] == "fully_allocated":
                items_fully_allocated += 1
            elif result["status"] == "partially_allocated":
                items_partially_allocated += 1
            else:
                items_failed += 1

        # Update order status
        if items_fully_allocated == len(order_items):
            order.status = Order.STATUS_ALLOCATED
            order.save(update_fields=["status"])
        elif items_failed == len(order_items):
            Notification.objects.create(
                user=user,
                message=f"Order {order.order_no} allocation failed: insufficient stock for all items",
                level=Notification.LEVEL_ERROR,
            )
            raise AllocationError(f"Insufficient stock to allocate any items for order {order.order_no}")
        else:
            Notification.objects.create(
                user=user,
                message=f"Order {order.order_no} partially allocated: {items_fully_allocated}/{len(order_items)} items fully allocated",
                level=Notification.LEVEL_WARNING,
            )

    return {
        "order_id": order.pk,
        "order_no": order.order_no,
        "status": order.status,
        "items_allocated": items_fully_allocated,
        "items_partial": items_partially_allocated,
        "items_failed": items_failed,
        "details": allocation_results,
    }


def _allocate_item_with_stack(order_item: OrderItem, user=None) -> Dict[str, Any]:
    """
    Allocate inventory for a single order item using a manual Stack of batches.

    - Build a stack of eligible batches such that pop() yields the next batch to consume.
      We want FEFO behavior (earliest expiry first), so we query ascending by expiry and
      push in reverse order, making pop return earliest.
    """
    from .structures import ManualStack

    item = order_item.item
    qty_needed = order_item.qty_requested - order_item.qty_allocated

    if qty_needed <= Decimal("0"):
        return {
            "order_item_id": order_item.pk,
            "item_sku": item.sku,
            "status": "fully_allocated",
            "qty_requested": float(order_item.qty_requested),
            "qty_allocated": float(order_item.qty_allocated),
            "allocations": [],
        }

    today = timezone.now().date()
    eligible = list(
        Batch.objects.filter(
            item=item,
            status=Batch.STATUS_AVAILABLE,
            available_qty__gt=Decimal("0"),
        )
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=today))
        .order_by("expiry_date", "pk")
        .values("id")
    )

    # Push in reverse so that pop gives earliest expiry first
    stack: ManualStack[int] = ManualStack(max(16, len(eligible)))
    for row in reversed(eligible):
        stack.push(row["id"])  # store batch ids

    allocations_made = []
    qty_remaining = qty_needed

    while (qty_remaining > 0) and (not stack.is_empty()):
        batch_id = stack.pop()
        # Lock batch row to update safely
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.available_qty <= 0 or batch.status != Batch.STATUS_AVAILABLE:
            continue
        qty_to_allocate = min(batch.available_qty, qty_remaining)

        Batch.objects.filter(pk=batch.pk).update(
            available_qty=F("available_qty") - qty_to_allocate
        )

        allocation = Allocation.objects.create(
            order_item=order_item,
            batch=batch,
            qty_allocated=qty_to_allocate,
        )

        TransactionLog.objects.create(
            user=user,
            type=TransactionLog.TYPE_RESERVE,
            qty=qty_to_allocate,
            item=item,
            batch=batch,
            order=order_item.order,
            meta={
                "order_no": order_item.order.order_no,
                "order_item_id": order_item.pk,
                "allocation_id": allocation.pk,
                "algo": "queue+stack",
            },
        )

        allocations_made.append({
            "batch_lot": batch.lot_no,
            "qty": float(qty_to_allocate),
        })
        qty_remaining -= qty_to_allocate

    total_allocated = qty_needed - qty_remaining
    OrderItem.objects.filter(pk=order_item.pk).update(
        qty_allocated=F("qty_allocated") + total_allocated
    )
    order_item.refresh_from_db(fields=["qty_allocated"])

    if qty_remaining <= Decimal("0"):
        status = "fully_allocated"
    elif total_allocated > Decimal("0"):
        status = "partially_allocated"
    else:
        status = "allocation_failed"

    return {
        "order_item_id": order_item.pk,
        "item_sku": item.sku,
        "status": status,
        "qty_requested": float(order_item.qty_requested),
        "qty_allocated": float(order_item.qty_allocated),
        "qty_remaining": float(qty_remaining),
        "allocations": allocations_made,
    }
