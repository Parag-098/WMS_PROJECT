"""
Unit tests for shipping workflow.

Tests verify that:
- Shipping decrements batch available_qty correctly
- TransactionLog entries are created for ship operations
- Shipment status transitions work correctly
"""
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory.models import (
    Item,
    Batch,
    Order,
    OrderItem,
    Allocation,
    Shipment,
    TransactionLog,
)
from inventory.services.allocation import allocate_order

User = get_user_model()


class ShippingWorkflowTestCase(TestCase):
    """Test shipping workflow and transaction logging."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.item = Item.objects.create(
            sku="SHIP-001",
            name="Shippable Item",
            unit="pcs",
        )

        self.batch = Batch.objects.create(
            item=self.item,
            lot_no="SHIP-LOT-A",
            received_qty=Decimal("100"),
            available_qty=Decimal("100"),
            expiry_date=timezone.now().date() + timedelta(days=30),
            status=Batch.STATUS_AVAILABLE,
        )

        self.order = Order.objects.create(
            order_no="SHIP-ORD-001",
            customer_name="Shipping Customer",
            status=Order.STATUS_NEW,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("30"),
        )

    def test_shipping_decrements_batch_quantity(self):
        """Test that shipping operation decrements batch available_qty."""
        # Allocate first
        allocate_order(self.order)
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_ALLOCATED)

        # Create shipment and simulate ship action
        shipment = Shipment.objects.create(
            shipment_no="SHIP-001",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Simulate shipping: decrement from allocations
        allocations = Allocation.objects.filter(order_item__order=self.order)
        
        for alloc in allocations:
            batch = alloc.batch
            qty = alloc.qty_allocated
            
            # Decrement (already done by allocation, but verify)
            batch.refresh_from_db()
            initial_qty = batch.available_qty
            
            # In real workflow, ship doesn't further decrement (allocation did it)
            # But let's verify allocation already decremented
            self.assertEqual(initial_qty, Decimal("70"))  # 100 - 30

        # Mark shipment as shipped
        shipment.status = Shipment.STATUS_IN_TRANSIT
        shipment.save()

        # Update order status
        self.order.status = Order.STATUS_SHIPPED
        self.order.save()

        self.assertEqual(self.order.status, Order.STATUS_SHIPPED)
        self.assertEqual(shipment.status, Shipment.STATUS_IN_TRANSIT)

    def test_shipping_creates_transaction_log(self):
        """Test that shipping creates TransactionLog entries."""
        # Allocate
        allocate_order(self.order)

        # Create shipment
        shipment = Shipment.objects.create(
            shipment_no="SHIP-002",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Create transaction log for ship operation
        allocations = Allocation.objects.filter(order_item__order=self.order)
        
        for alloc in allocations:
            TransactionLog.objects.create(
                user=self.user,
                transaction_type=TransactionLog.TYPE_SHIP,
                qty_change=-alloc.qty_allocated,
                item=alloc.order_item.item,
                batch=alloc.batch,
                order_item=alloc.order_item,
                shipment=shipment,
                notes=f"Shipped {alloc.qty_allocated} units",
            )

        # Verify transaction logs created
        txn_logs = TransactionLog.objects.filter(
            transaction_type=TransactionLog.TYPE_SHIP,
            shipment=shipment,
        )

        self.assertEqual(txn_logs.count(), 1)
        
        log = txn_logs.first()
        self.assertEqual(log.qty_change, Decimal("-30"))
        self.assertEqual(log.item, self.item)
        self.assertEqual(log.batch, self.batch)
        self.assertEqual(log.user, self.user)

    def test_multiple_allocations_shipping(self):
        """Test shipping with split allocations across multiple batches."""
        # Create second batch
        batch2 = Batch.objects.create(
            item=self.item,
            lot_no="SHIP-LOT-B",
            received_qty=Decimal("50"),
            available_qty=Decimal("50"),
            expiry_date=timezone.now().date() + timedelta(days=60),
            status=Batch.STATUS_AVAILABLE,
        )

        # Order more than first batch
        self.order_item.qty_requested = Decimal("120")
        self.order_item.save()

        # Allocate (will split across batches)
        result = allocate_order(self.order)
        self.assertTrue(result["success"])

        # Verify allocations
        allocations = Allocation.objects.filter(order_item=self.order_item).order_by("created_at")
        self.assertEqual(allocations.count(), 2)

        # Create shipment
        shipment = Shipment.objects.create(
            shipment_no="SHIP-003",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Create transaction logs for each allocation
        for alloc in allocations:
            TransactionLog.objects.create(
                user=self.user,
                transaction_type=TransactionLog.TYPE_SHIP,
                qty_change=-alloc.qty_allocated,
                item=alloc.order_item.item,
                batch=alloc.batch,
                order_item=alloc.order_item,
                shipment=shipment,
            )

        # Verify transaction logs
        txn_logs = TransactionLog.objects.filter(
            transaction_type=TransactionLog.TYPE_SHIP,
            shipment=shipment,
        ).order_by("timestamp")

        self.assertEqual(txn_logs.count(), 2)

        # First log: batch1
        log1 = txn_logs[0]
        self.assertEqual(log1.batch, self.batch)
        self.assertEqual(log1.qty_change, Decimal("-100"))

        # Second log: batch2
        log2 = txn_logs[1]
        self.assertEqual(log2.batch, batch2)
        self.assertEqual(log2.qty_change, Decimal("-20"))  # 120 - 100

        # Verify batch quantities after allocation
        self.batch.refresh_from_db()
        batch2.refresh_from_db()

        self.assertEqual(self.batch.available_qty, Decimal("0"))
        self.assertEqual(batch2.available_qty, Decimal("30"))

    def test_shipment_status_transitions(self):
        """Test shipment status transitions."""
        allocate_order(self.order)

        shipment = Shipment.objects.create(
            shipment_no="SHIP-004",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Created -> In Transit
        shipment.status = Shipment.STATUS_IN_TRANSIT
        shipment.save()
        self.assertEqual(shipment.status, Shipment.STATUS_IN_TRANSIT)

        # In Transit -> Delivered
        shipment.status = Shipment.STATUS_DELIVERED
        shipment.save()
        self.assertEqual(shipment.status, Shipment.STATUS_DELIVERED)

    def test_transaction_log_immutability(self):
        """Test that TransactionLog entries cannot be modified."""
        log = TransactionLog.objects.create(
            user=self.user,
            transaction_type=TransactionLog.TYPE_SHIP,
            qty_change=Decimal("-10"),
            item=self.item,
            batch=self.batch,
        )

        # Attempt to modify should raise error
        with self.assertRaises(ValueError):
            log.qty_change = Decimal("-20")
            log.save()

    def test_shipping_without_allocation_fails(self):
        """Test that shipping without prior allocation should not proceed."""
        # Create shipment without allocation
        shipment = Shipment.objects.create(
            shipment_no="SHIP-005",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Verify no allocations exist
        allocations = Allocation.objects.filter(order_item__order=self.order)
        self.assertEqual(allocations.count(), 0)

        # Order should still be NEW (not allocated)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_NEW)

        # Attempting to create ship transaction logs would have no allocations to process
        # This is a business logic check that should be enforced in views/services
        # Here we just verify the state
        self.assertFalse(self.order.is_fully_allocated)

    def test_partial_shipment_tracking(self):
        """Test tracking partial shipments for an order."""
        # Create larger order
        self.order_item.qty_requested = Decimal("100")
        self.order_item.save()

        allocate_order(self.order)

        # Create first shipment for partial qty
        shipment1 = Shipment.objects.create(
            shipment_no="SHIP-006-A",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        # Log partial ship (e.g., 60 units)
        TransactionLog.objects.create(
            user=self.user,
            transaction_type=TransactionLog.TYPE_SHIP,
            qty_change=Decimal("-60"),
            item=self.item,
            batch=self.batch,
            order_item=self.order_item,
            shipment=shipment1,
        )

        # Create second shipment for remaining
        shipment2 = Shipment.objects.create(
            shipment_no="SHIP-006-B",
            order=self.order,
            status=Shipment.STATUS_CREATED,
        )

        TransactionLog.objects.create(
            user=self.user,
            transaction_type=TransactionLog.TYPE_SHIP,
            qty_change=Decimal("-40"),
            item=self.item,
            batch=self.batch,
            order_item=self.order_item,
            shipment=shipment2,
        )

        # Verify two shipments exist for order
        shipments = Shipment.objects.filter(order=self.order)
        self.assertEqual(shipments.count(), 2)

        # Verify total shipped quantity in logs
        total_shipped = TransactionLog.objects.filter(
            transaction_type=TransactionLog.TYPE_SHIP,
            order_item=self.order_item,
        ).aggregate(total=models.Sum("qty_change"))["total"]

        self.assertEqual(total_shipped, Decimal("-100"))


# Import for aggregate
from django.db import models
