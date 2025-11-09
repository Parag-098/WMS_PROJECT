"""
Undo/Redo service for reversible inventory operations.
"""
import json
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ..models import UndoStack, RedoStack, Batch, Order, OrderItem, Allocation, TransactionLog, Return

logger = logging.getLogger(__name__)


class UndoRedoError(Exception):
    """Base exception for undo/redo operations."""
    pass


# =============================
# Push Operations to Stack
# =============================

def push_undo_operation(operation_type, data, user, description):
    """
    Push a reversible operation to the undo stack.
    
    Args:
        operation_type: Type of operation (allocation, receive, ship, restock, etc.)
        data: JSON-serializable dict containing operation details
        user: User who performed the operation
        description: Human-readable description
    """
    UndoStack.push(
        operation_type=operation_type,
        data=data,
        user=user,
        description=description,
    )
    logger.info(f"Pushed undo operation: {operation_type} - {description}")


def push_redo_operation(operation_type, data, user, description):
    """
    Push a reversible operation to the redo stack.
    
    Args:
        operation_type: Type of operation
        data: JSON-serializable dict containing operation details
        user: User who performed the operation
        description: Human-readable description
    """
    RedoStack.push(
        operation_type=operation_type,
        data=data,
        user=user,
        description=description,
    )
    logger.info(f"Pushed redo operation: {operation_type} - {description}")


# =============================
# Undo Operations
# =============================

def undo_allocation(data, user):
    """
    Undo an allocation operation.
    
    Reverses allocation by deleting Allocation records and restoring batch availability.
    """
    order_id = data.get("order_id")
    allocations = data.get("allocations", [])
    
    with transaction.atomic():
        for alloc_data in allocations:
            allocation_id = alloc_data.get("allocation_id")
            batch_id = alloc_data.get("batch_id")
            qty_allocated = Decimal(str(alloc_data.get("qty_allocated")))
            
            # Delete allocation record
            Allocation.objects.filter(pk=allocation_id).delete()
            
            # Restore batch availability
            batch = Batch.objects.select_for_update().get(pk=batch_id)
            batch.available_qty += qty_allocated
            batch.save()
            
            # Log undo transaction
            TransactionLog.objects.create(
                batch=batch,
                qty_change=qty_allocated,
                transaction_type="undo_allocation",
                user=user,
                notes=f"Undid allocation for order {order_id}",
            )
        
        # Update order status back to pending
        order = Order.objects.get(pk=order_id)
        order.status = Order.STATUS_PENDING
        order.save()
    
    return f"Undid allocation for order {order_id}: {len(allocations)} allocation(s) reversed"


def undo_receive(data, user):
    """
    Undo a receive operation.
    
    Deletes batch records created during receive.
    """
    batch_ids = data.get("batch_ids", [])
    
    with transaction.atomic():
        for batch_id in batch_ids:
            batch = Batch.objects.select_for_update().get(pk=batch_id)
            
            # Check if batch has been used in allocations
            if batch.allocations.exists():
                raise UndoRedoError(
                    f"Cannot undo receive: Batch {batch.lot_no} has active allocations"
                )
            
            # Log undo transaction
            TransactionLog.objects.create(
                batch=batch,
                qty_change=-batch.received_qty,
                transaction_type="undo_receive",
                user=user,
                notes=f"Undid receive of batch {batch.lot_no}",
            )
            
            # Delete batch
            batch.delete()
    
    return f"Undid receive operation: {len(batch_ids)} batch(es) deleted"


def undo_ship(data, user):
    """
    Undo a ship operation.
    
    Restores batch quantities, reverses order status, deletes shipment.
    """
    shipment_id = data.get("shipment_id")
    order_id = data.get("order_id")
    consumptions = data.get("consumptions", [])
    
    with transaction.atomic():
        # Restore batch quantities
        for consumption in consumptions:
            batch_id = consumption.get("batch_id")
            qty_consumed = Decimal(str(consumption.get("qty_consumed")))
            
            batch = Batch.objects.select_for_update().get(pk=batch_id)
            batch.available_qty += qty_consumed
            batch.save()
            
            # Log undo transaction
            TransactionLog.objects.create(
                batch=batch,
                qty_change=qty_consumed,
                transaction_type="undo_ship",
                user=user,
                notes=f"Undid shipment {shipment_id}",
            )
        
        # Revert order status
        order = Order.objects.get(pk=order_id)
        order.status = Order.STATUS_PACKED
        order.save()
        
        # Delete shipment record
        from ..models import Shipment
        Shipment.objects.filter(pk=shipment_id).delete()
    
    return f"Undid shipment {shipment_id}: {len(consumptions)} batch(es) restored"


def undo_restock(data, user):
    """
    Undo a restock operation from return processing.
    
    Reverses batch quantity adjustments from return restocking.
    """
    return_id = data.get("return_id")
    batch_id = data.get("batch_id")
    qty_restocked = Decimal(str(data.get("qty_restocked")))
    
    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        batch.available_qty -= qty_restocked
        batch.save()
        
        # Log undo transaction
        TransactionLog.objects.create(
            batch=batch,
            qty_change=-qty_restocked,
            transaction_type="undo_restock",
            user=user,
            notes=f"Undid restock from return {return_id}",
        )
        
        # Update return status back to pending
        return_obj = Return.objects.get(pk=return_id)
        return_obj.status = Return.STATUS_PENDING
        return_obj.save()
    
    return f"Undid restock from return {return_id}"


# =============================
# Redo Operations (mirror of undo)
# =============================

def redo_allocation(data, user):
    """Redo an allocation operation."""
    # This would re-run the allocation logic
    # For simplicity, we can call the allocation service again
    from ..services.allocation import allocate_order
    
    order_id = data.get("order_id")
    result = allocate_order(order_id, user=user)
    
    return f"Redid allocation for order {order_id}"


def redo_receive(data, user):
    """Redo a receive operation."""
    # Recreate batches from saved data
    batch_data_list = data.get("batches", [])
    
    with transaction.atomic():
        for batch_data in batch_data_list:
            batch = Batch.objects.create(
                item_id=batch_data["item_id"],
                lot_no=batch_data["lot_no"],
                received_qty=Decimal(str(batch_data["received_qty"])),
                available_qty=Decimal(str(batch_data["available_qty"])),
                expiry_date=batch_data.get("expiry_date"),
                status=batch_data.get("status", Batch.STATUS_AVAILABLE),
            )
            
            TransactionLog.objects.create(
                batch=batch,
                qty_change=batch.received_qty,
                transaction_type="redo_receive",
                user=user,
                notes=f"Redid receive of batch {batch.lot_no}",
            )
    
    return f"Redid receive operation: {len(batch_data_list)} batch(es) created"


# =============================
# Main Undo/Redo Entry Points
# =============================

UNDO_HANDLERS = {
    "allocation": undo_allocation,
    "receive": undo_receive,
    "ship": undo_ship,
    "restock": undo_restock,
}

REDO_HANDLERS = {
    "allocation": redo_allocation,
    "receive": redo_receive,
}


def perform_undo(user, count=1):
    """
    Perform undo operation(s).
    
    Args:
        user: User performing the undo
        count: Number of operations to undo
    
    Returns:
        List of result messages
    """
    results = []
    
    for _ in range(count):
        undo_op = UndoStack.pop()
        
        if not undo_op:
            results.append("No more operations to undo")
            break
        
        handler = UNDO_HANDLERS.get(undo_op.operation_type)
        
        if not handler:
            logger.warning(f"No undo handler for operation type: {undo_op.operation_type}")
            results.append(f"Cannot undo operation: {undo_op.operation_type}")
            continue
        
        try:
            result_msg = handler(undo_op.data, user)
            results.append(result_msg)
            
            # Push to redo stack
            push_redo_operation(
                operation_type=undo_op.operation_type,
                data=undo_op.data,
                user=user,
                description=f"Redo: {undo_op.description}",
            )
            
        except Exception as e:
            logger.error(f"Undo failed for {undo_op.operation_type}: {e}")
            results.append(f"Undo failed: {str(e)}")
            # Re-push to undo stack if failed
            UndoStack.push(
                operation_type=undo_op.operation_type,
                data=undo_op.data,
                user=undo_op.user,
                description=undo_op.description,
            )
    
    return results


def perform_redo(user, count=1):
    """
    Perform redo operation(s).
    
    Args:
        user: User performing the redo
        count: Number of operations to redo
    
    Returns:
        List of result messages
    """
    results = []
    
    for _ in range(count):
        redo_op = RedoStack.pop()
        
        if not redo_op:
            results.append("No more operations to redo")
            break
        
        handler = REDO_HANDLERS.get(redo_op.operation_type)
        
        if not handler:
            logger.warning(f"No redo handler for operation type: {redo_op.operation_type}")
            results.append(f"Cannot redo operation: {redo_op.operation_type}")
            continue
        
        try:
            result_msg = handler(redo_op.data, user)
            results.append(result_msg)
            
            # Push back to undo stack
            push_undo_operation(
                operation_type=redo_op.operation_type,
                data=redo_op.data,
                user=user,
                description=redo_op.description,
            )
            
        except Exception as e:
            logger.error(f"Redo failed for {redo_op.operation_type}: {e}")
            results.append(f"Redo failed: {str(e)}")
            # Re-push to redo stack if failed
            RedoStack.push(
                operation_type=redo_op.operation_type,
                data=redo_op.data,
                user=redo_op.user,
                description=redo_op.description,
            )
    
    return results
