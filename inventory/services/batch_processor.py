"""
Batch order processor with Queue/Stack visualization.

Processes all NEW orders using manual Queue (FIFO) and Stack (LIFO) algorithms.
Provides detailed trace logs for visualization in the UI.
"""
from typing import List, Dict, Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from inventory.models import Order, OrderItem, Batch, Allocation, TransactionLog
from .structures import ManualQueue, ManualStack


class OrderQueueTrace:
    """Collects step-by-step trace of queue/stack operations for visualization."""
    
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.order_queue_snapshots: List[List[str]] = []
        self.batch_stack_snapshots: List[List[str]] = []
    
    def log_step(self, action: str, details: Dict[str, Any]):
        """Log a single operation step."""
        self.steps.append({
            "action": action,
            "timestamp": timezone.now().isoformat(),
            **details
        })
    
    def snapshot_order_queue(self, queue_state: List[str]):
        """Capture current state of order queue."""
        self.order_queue_snapshots.append(queue_state.copy())
    
    def snapshot_batch_stack(self, stack_state: List[str]):
        """Capture current state of batch stack."""
        self.batch_stack_snapshots.append(stack_state.copy())
    
    def get_trace(self) -> Dict[str, Any]:
        """Return complete trace for visualization."""
        return {
            "steps": self.steps,
            "order_queue_snapshots": self.order_queue_snapshots,
            "batch_stack_snapshots": self.batch_stack_snapshots,
            "total_steps": len(self.steps),
        }


def process_order_queue_batch(user=None, trace_enabled: bool = True) -> Dict[str, Any]:
    """
    Process all NEW orders in batch using manual Queue + Stack algorithms.
    
    Algorithm:
    1. Build a queue of all NEW orders (FIFO)
    2. Dequeue each order
    3. For each order, build a queue of its order items
    4. For each order item, build a stack of eligible batches (LIFO with FEFO)
    5. Pop batches and allocate until item is fulfilled
    
    Returns:
        Dict with processing results and optional trace for visualization
    """
    trace = OrderQueueTrace() if trace_enabled else None
    
    # Get all NEW orders ordered by creation time (FIFO)
    new_orders = list(
        Order.objects.filter(status=Order.STATUS_NEW)
        .prefetch_related('items__item')
        .order_by('created_at')
    )
    
    if not new_orders:
        return {
            "status": "no_orders",
            "message": "No NEW orders to process",
            "orders_processed": 0,
            "trace": trace.get_trace() if trace else None,
        }
    
    # Build order queue
    order_queue: ManualQueue[Order] = ManualQueue(max(16, len(new_orders)))
    for order in new_orders:
        order_queue.enqueue(order)
    
    if trace:
        trace.log_step("queue_initialized", {
            "action_type": "queue_init",
            "queue_type": "order_queue",
            "total_orders": len(new_orders),
            "order_ids": [o.order_no for o in new_orders]
        })
        trace.snapshot_order_queue([o.order_no for o in new_orders])
    
    results = []
    orders_processed = 0
    orders_fully_allocated = 0
    orders_partially_allocated = 0
    orders_failed = 0
    
    with transaction.atomic():
        while not order_queue.is_empty():
            order = order_queue.dequeue()
            orders_processed += 1
            
            if trace:
                # Get current queue state (remaining orders)
                remaining = []
                temp_q = ManualQueue(order_queue.size())
                while not order_queue.is_empty():
                    o = order_queue.dequeue()
                    remaining.append(o.order_no)
                    temp_q.enqueue(o)
                # Restore queue
                while not temp_q.is_empty():
                    order_queue.enqueue(temp_q.dequeue())
                
                trace.log_step("order_dequeued", {
                    "action_type": "queue_dequeue",
                    "order_no": order.order_no,
                    "order_id": order.pk,
                    "remaining_in_queue": remaining
                })
                trace.snapshot_order_queue(remaining)
            
            # Process this order
            order_result = _process_single_order_with_trace(order, user, trace)
            results.append(order_result)
            
            if order_result["status"] == "fully_allocated":
                orders_fully_allocated += 1
            elif order_result["status"] == "partially_allocated":
                orders_partially_allocated += 1
            else:
                orders_failed += 1
    
    return {
        "status": "completed",
        "orders_processed": orders_processed,
        "orders_fully_allocated": orders_fully_allocated,
        "orders_partially_allocated": orders_partially_allocated,
        "orders_failed": orders_failed,
        "results": results,
        "trace": trace.get_trace() if trace else None,
    }


def _process_single_order_with_trace(order: Order, user, trace: OrderQueueTrace = None) -> Dict[str, Any]:
    """Process a single order with optional tracing."""
    order_items = list(order.items.select_related("item").all())
    
    if not order_items:
        return {
            "order_no": order.order_no,
            "status": "failed",
            "message": "No items in order"
        }
    
    # Build item queue
    item_queue: ManualQueue[OrderItem] = ManualQueue(max(16, len(order_items)))
    for oi in order_items:
        item_queue.enqueue(oi)
    
    if trace:
        trace.log_step("order_items_queued", {
            "action_type": "item_queue_init",
            "order_no": order.order_no,
            "total_items": len(order_items),
            "items": [{"sku": oi.item.sku, "qty": float(oi.qty_requested)} for oi in order_items]
        })
    
    items_fully_allocated = 0
    items_partially_allocated = 0
    items_failed = 0
    
    while not item_queue.is_empty():
        order_item = item_queue.dequeue()
        
        if trace:
            trace.log_step("item_dequeued", {
                "action_type": "item_dequeue",
                "order_no": order.order_no,
                "sku": order_item.item.sku,
                "qty_requested": float(order_item.qty_requested)
            })
        
        result = _allocate_item_with_stack_trace(order_item, user, trace)
        
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
        status = "fully_allocated"
    elif items_failed == len(order_items):
        status = "allocation_failed"
    else:
        status = "partially_allocated"
    
    if trace:
        trace.log_step("order_completed", {
            "action_type": "order_complete",
            "order_no": order.order_no,
            "status": status,
            "items_fully": items_fully_allocated,
            "items_partial": items_partially_allocated,
            "items_failed": items_failed
        })
    
    return {
        "order_no": order.order_no,
        "order_id": order.pk,
        "status": status,
        "items_fully_allocated": items_fully_allocated,
        "items_partially_allocated": items_partially_allocated,
        "items_failed": items_failed,
    }


def _allocate_item_with_stack_trace(order_item: OrderItem, user, trace: OrderQueueTrace = None) -> Dict[str, Any]:
    """Allocate inventory for a single order item using Stack with optional tracing."""
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
        .values("id", "lot_no", "available_qty", "expiry_date")
    )
    
    # Build stack (push in reverse for FEFO via LIFO)
    stack: ManualStack[Dict] = ManualStack(max(16, len(eligible)))
    for batch_data in reversed(eligible):
        stack.push(batch_data)
    
    if trace:
        stack_state = [f"{b['lot_no']}({b['available_qty']})" for b in reversed(eligible)]
        trace.log_step("batch_stack_built", {
            "action_type": "stack_init",
            "sku": item.sku,
            "total_batches": len(eligible),
            "batches": stack_state
        })
        trace.snapshot_batch_stack(stack_state)
    
    allocations_made = []
    qty_remaining = qty_needed
    
    while (qty_remaining > 0) and (not stack.is_empty()):
        batch_data = stack.pop()
        batch_id = batch_data["id"]
        
        if trace:
            # Snapshot current stack
            temp_stack = ManualStack(stack.size())
            temp_list = []
            while not stack.is_empty():
                b = stack.pop()
                temp_list.append(f"{b['lot_no']}({b['available_qty']})")
                temp_stack.push(b)
            # Restore
            while not temp_stack.is_empty():
                stack.push(temp_stack.pop())
            
            trace.log_step("batch_popped", {
                "action_type": "stack_pop",
                "sku": item.sku,
                "batch_lot": batch_data["lot_no"],
                "available_qty": float(batch_data["available_qty"]),
                "remaining_in_stack": temp_list
            })
            trace.snapshot_batch_stack(temp_list)
        
        # Lock and allocate
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
                "algo": "batch_queue_stack",
            },
        )
        
        allocations_made.append({
            "batch_lot": batch.lot_no,
            "qty": float(qty_to_allocate),
        })
        qty_remaining -= qty_to_allocate
        
        if trace:
            trace.log_step("allocation_made", {
                "action_type": "allocate",
                "sku": item.sku,
                "batch_lot": batch.lot_no,
                "qty_allocated": float(qty_to_allocate),
                "qty_remaining": float(qty_remaining)
            })
    
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
    
    if trace:
        trace.log_step("item_allocation_complete", {
            "action_type": "item_complete",
            "sku": item.sku,
            "status": status,
            "total_allocated": float(total_allocated),
            "allocations_count": len(allocations_made)
        })
    
    return {
        "order_item_id": order_item.pk,
        "item_sku": item.sku,
        "status": status,
        "qty_requested": float(order_item.qty_requested),
        "qty_allocated": float(order_item.qty_allocated),
        "qty_remaining": float(qty_remaining),
        "allocations": allocations_made,
    }
