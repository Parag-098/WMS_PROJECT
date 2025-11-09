"""
Unit tests for FEFO (First-Expiry First-Out) allocation logic.

Tests verify that:
- Batches with earlier expiry dates are allocated first
- Split allocations work correctly when single batch cannot fulfill order
- Allocations are correctly recorded with proper quantities
"""
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone

from inventory.models import Item, Batch, Order, OrderItem, Allocation
from inventory.services.allocation import allocate_order


class FEFOAllocationTestCase(TestCase):
    """Test FEFO allocation strategy."""

    def setUp(self):
        """Create test item and batches with different expiry dates."""
        self.item = Item.objects.create(
            sku="TEST-001",
            name="Test Item",
            unit="pcs",
            reorder_threshold=Decimal("10"),
        )

        today = timezone.now().date()

        # Batch 1: expires sooner, less quantity
        self.batch1 = Batch.objects.create(
            item=self.item,
            lot_no="LOT-A",
            received_qty=Decimal("50"),
            available_qty=Decimal("50"),
            expiry_date=today + timedelta(days=5),
            status=Batch.STATUS_AVAILABLE,
        )

        # Batch 2: expires later, more quantity
        self.batch2 = Batch.objects.create(
            item=self.item,
            lot_no="LOT-B",
            received_qty=Decimal("100"),
            available_qty=Decimal("100"),
            expiry_date=today + timedelta(days=30),
            status=Batch.STATUS_AVAILABLE,
        )

        # Batch 3: no expiry (should be used last)
        self.batch3 = Batch.objects.create(
            item=self.item,
            lot_no="LOT-C",
            received_qty=Decimal("75"),
            available_qty=Decimal("75"),
            expiry_date=None,
            status=Batch.STATUS_AVAILABLE,
        )

        # Create order
        self.order = Order.objects.create(
            order_no="ORD-001",
            customer_name="Test Customer",
            status=Order.STATUS_NEW,
        )

    def test_single_batch_allocation(self):
        """Test allocation when single batch can fulfill order."""
        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("30"),
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])
        self.assertEqual(result["allocated_count"], 1)

        # Verify allocation used earliest expiry batch
        allocations = Allocation.objects.filter(order_item=order_item)
        self.assertEqual(allocations.count(), 1)
        self.assertEqual(allocations.first().batch, self.batch1)
        self.assertEqual(allocations.first().qty_allocated, Decimal("30"))

        # Verify batch quantities
        self.batch1.refresh_from_db()
        self.assertEqual(self.batch1.available_qty, Decimal("20"))

    def test_split_allocation_across_batches(self):
        """Test FEFO when order requires multiple batches."""
        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("120"),  # More than batch1+batch2
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])
        self.assertEqual(result["allocated_count"], 1)

        # Verify allocations follow FEFO order
        allocations = Allocation.objects.filter(order_item=order_item).order_by("created_at")
        self.assertEqual(allocations.count(), 3)

        # First allocation: batch1 (expires soonest)
        alloc1 = allocations[0]
        self.assertEqual(alloc1.batch, self.batch1)
        self.assertEqual(alloc1.qty_allocated, Decimal("50"))

        # Second allocation: batch2 (expires next)
        alloc2 = allocations[1]
        self.assertEqual(alloc2.batch, self.batch2)
        self.assertEqual(alloc2.qty_allocated, Decimal("70"))  # Remaining from 120-50

        # Third allocation should not exist since we only need 120
        # Actually, let's recalculate: 120 total, batch1=50, batch2 should take 70
        # So only 2 allocations
        self.assertEqual(allocations.count(), 2)

        # Verify batch quantities
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()
        self.batch3.refresh_from_db()

        self.assertEqual(self.batch1.available_qty, Decimal("0"))
        self.assertEqual(self.batch2.available_qty, Decimal("30"))
        self.assertEqual(self.batch3.available_qty, Decimal("75"))  # Untouched

    def test_fefo_respects_expiry_order(self):
        """Test that batches are consumed in expiry order."""
        # Order quantity that requires all three batches
        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("200"),  # Requires batch1+batch2+batch3
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])

        allocations = Allocation.objects.filter(order_item=order_item).order_by("created_at")
        self.assertEqual(allocations.count(), 3)

        # Verify order: earliest expiry first
        self.assertEqual(allocations[0].batch, self.batch1)
        self.assertEqual(allocations[0].qty_allocated, Decimal("50"))

        self.assertEqual(allocations[1].batch, self.batch2)
        self.assertEqual(allocations[1].qty_allocated, Decimal("100"))

        self.assertEqual(allocations[2].batch, self.batch3)
        self.assertEqual(allocations[2].qty_allocated, Decimal("50"))  # 200-50-100

        # All batches partially or fully consumed
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()
        self.batch3.refresh_from_db()

        self.assertEqual(self.batch1.available_qty, Decimal("0"))
        self.assertEqual(self.batch2.available_qty, Decimal("0"))
        self.assertEqual(self.batch3.available_qty, Decimal("25"))

    def test_insufficient_stock_allocation(self):
        """Test allocation failure when insufficient stock available."""
        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("300"),  # More than total available (225)
        )

        result = allocate_order(self.order)

        self.assertFalse(result["success"])
        self.assertIn("Insufficient stock", result["message"])

        # No allocations should be created
        allocations = Allocation.objects.filter(order_item=order_item)
        self.assertEqual(allocations.count(), 0)

        # Batch quantities unchanged
        self.batch1.refresh_from_db()
        self.batch2.refresh_from_db()
        self.batch3.refresh_from_db()

        self.assertEqual(self.batch1.available_qty, Decimal("50"))
        self.assertEqual(self.batch2.available_qty, Decimal("100"))
        self.assertEqual(self.batch3.available_qty, Decimal("75"))

    def test_expired_batches_not_allocated(self):
        """Test that expired batches are not used for allocation."""
        # Mark batch1 as expired
        self.batch1.status = Batch.STATUS_EXPIRED
        self.batch1.save()

        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("80"),
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])

        # Should use batch2 first (not expired batch1)
        allocations = Allocation.objects.filter(order_item=order_item)
        self.assertEqual(allocations.count(), 1)
        self.assertEqual(allocations.first().batch, self.batch2)
        self.assertEqual(allocations.first().qty_allocated, Decimal("80"))

    def test_multiple_order_items_allocation(self):
        """Test allocation for order with multiple items."""
        # Create second item with batches
        item2 = Item.objects.create(
            sku="TEST-002",
            name="Test Item 2",
            unit="pcs",
        )

        batch_item2 = Batch.objects.create(
            item=item2,
            lot_no="LOT-D",
            received_qty=Decimal("100"),
            available_qty=Decimal("100"),
            expiry_date=timezone.now().date() + timedelta(days=10),
            status=Batch.STATUS_AVAILABLE,
        )

        # Create order items
        order_item1 = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("40"),
        )

        order_item2 = OrderItem.objects.create(
            order=self.order,
            item=item2,
            qty_requested=Decimal("60"),
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])
        self.assertEqual(result["allocated_count"], 2)

        # Verify both items allocated
        allocs1 = Allocation.objects.filter(order_item=order_item1)
        allocs2 = Allocation.objects.filter(order_item=order_item2)

        self.assertEqual(allocs1.count(), 1)
        self.assertEqual(allocs2.count(), 1)

        self.assertEqual(allocs1.first().qty_allocated, Decimal("40"))
        self.assertEqual(allocs2.first().qty_allocated, Decimal("60"))

    def test_on_hold_batches_not_allocated(self):
        """Test that batches on hold are not used for allocation."""
        self.batch1.status = Batch.STATUS_HOLD
        self.batch1.save()

        order_item = OrderItem.objects.create(
            order=self.order,
            item=self.item,
            qty_requested=Decimal("60"),
        )

        result = allocate_order(self.order)

        self.assertTrue(result["success"])

        # Should skip batch1 (on hold) and use batch2
        allocations = Allocation.objects.filter(order_item=order_item)
        self.assertEqual(allocations.count(), 1)
        self.assertEqual(allocations.first().batch, self.batch2)
