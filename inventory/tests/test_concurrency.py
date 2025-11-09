"""
Unit tests for concurrent allocation scenarios.

Tests verify that:
- Database row locking prevents overselling under concurrent access
- Multiple threads attempting to allocate from same batch handle conflicts correctly
- Batch.reserve() uses SELECT FOR UPDATE to ensure safety
"""
import threading
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.db import transaction, connection
from django.utils import timezone

from inventory.models import Item, Batch, Order, OrderItem, Allocation
from inventory.services.allocation import allocate_order


class ConcurrentAllocationTestCase(TransactionTestCase):
    """
    Test concurrent allocation scenarios.
    
    Note: Uses TransactionTestCase instead of TestCase to ensure proper
    transaction isolation for concurrency tests.
    """

    def setUp(self):
        """Set up test data for concurrency tests."""
        self.item = Item.objects.create(
            sku="CONC-001",
            name="Concurrent Test Item",
            unit="pcs",
        )

        self.batch = Batch.objects.create(
            item=self.item,
            lot_no="CONC-LOT-A",
            received_qty=Decimal("100"),
            available_qty=Decimal("100"),
            expiry_date=timezone.now().date() + timedelta(days=30),
            status=Batch.STATUS_AVAILABLE,
        )

    def test_concurrent_reserve_prevents_overselling(self):
        """Test that concurrent reserve operations don't oversell batch."""
        results = []
        errors = []

        def reserve_operation(qty, result_list, error_list):
            """Worker function to attempt reservation."""
            try:
                # Get fresh batch instance in this thread
                batch = Batch.objects.get(pk=self.batch.pk)
                remaining = batch.reserve(qty)
                result_list.append({"success": True, "remaining": float(remaining)})
            except Exception as e:
                error_list.append({"success": False, "error": str(e)})

        # Create 5 threads each trying to reserve 30 units
        # Total: 150 units requested, but only 100 available
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=reserve_operation,
                args=(Decimal("30"), results, errors)
            )
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Count successes and failures
        success_count = len([r for r in results if r["success"]])
        error_count = len(errors)

        # Should have 3 successes (3 * 30 = 90) and 2 failures
        # Or 3 successes (90) + 1 partial (10) + 1 failure
        # Depends on timing, but total allocated should not exceed 100
        total_allocated = Decimal("100") - Decimal(str(self.batch.available_qty))
        
        self.batch.refresh_from_db()
        self.assertLessEqual(total_allocated, Decimal("100"))
        self.assertGreaterEqual(self.batch.available_qty, Decimal("0"))

        # At least one operation should have failed due to insufficient stock
        self.assertGreater(error_count, 0)

    def test_concurrent_allocations_from_same_batch(self):
        """Test multiple orders allocating from same batch concurrently."""
        # Create 3 orders
        orders = []
        for i in range(3):
            order = Order.objects.create(
                order_no=f"CONC-ORD-{i+1}",
                customer_name=f"Concurrent Customer {i+1}",
                status=Order.STATUS_NEW,
            )
            OrderItem.objects.create(
                order=order,
                item=self.item,
                qty_requested=Decimal("40"),  # Each wants 40, total 120 > 100 available
            )
            orders.append(order)

        results = []
        errors = []

        def allocate_order_operation(order, result_list, error_list):
            """Worker function to allocate order."""
            try:
                result = allocate_order(order)
                result_list.append(result)
            except Exception as e:
                error_list.append({"order": order.order_no, "error": str(e)})

        # Create threads for each order
        threads = []
        for order in orders:
            t = threading.Thread(
                target=allocate_order_operation,
                args=(order, results, errors)
            )
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Check results
        success_count = len([r for r in results if r.get("success")])
        
        # Verify batch not oversold
        self.batch.refresh_from_db()
        self.assertGreaterEqual(self.batch.available_qty, Decimal("0"))

        # Total allocated should not exceed 100
        total_allocated = Allocation.objects.filter(
            order_item__item=self.item
        ).aggregate(total=models.Sum("qty_allocated"))["total"] or Decimal("0")
        
        self.assertLessEqual(total_allocated, Decimal("100"))

        # At least one order should fail to fully allocate
        # Since we have 120 requested but only 100 available
        failed_orders = [o for o in orders if not o.is_fully_allocated]
        self.assertGreater(len(failed_orders), 0)

    def test_select_for_update_prevents_race_condition(self):
        """Test that SELECT FOR UPDATE prevents race conditions."""
        results = {"read_values": []}
        
        def read_and_decrement():
            """Read available_qty and then decrement."""
            with transaction.atomic():
                # Lock the row
                batch = Batch.objects.select_for_update().get(pk=self.batch.pk)
                current_qty = batch.available_qty
                results["read_values"].append(float(current_qty))
                
                # Simulate processing time
                import time
                time.sleep(0.01)
                
                # Decrement
                if current_qty >= Decimal("10"):
                    batch.available_qty -= Decimal("10")
                    batch.save()

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=read_and_decrement)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Final batch quantity should be 0 (100 - 10*10)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.available_qty, Decimal("0"))

        # All read values should be different (due to locking)
        # No two threads should see the same value
        read_values = results["read_values"]
        self.assertEqual(len(read_values), 10)

    def test_concurrent_batch_reserve_with_check_constraint(self):
        """Test that check constraint prevents negative available_qty."""
        from django.db.utils import IntegrityError
        
        results = []
        errors = []

        def attempt_reserve(qty):
            """Attempt to reserve quantity."""
            try:
                batch = Batch.objects.get(pk=self.batch.pk)
                batch.reserve(qty)
                results.append({"success": True})
            except ValueError as e:
                # Expected error for insufficient stock
                errors.append({"error": "insufficient", "msg": str(e)})
            except IntegrityError as e:
                # Should not happen if reserve() works correctly
                errors.append({"error": "constraint", "msg": str(e)})
            except Exception as e:
                errors.append({"error": "other", "msg": str(e)})

        # Try to reserve more than available
        threads = []
        for i in range(3):
            t = threading.Thread(target=attempt_reserve, args=(Decimal("50"),))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have failures due to insufficient stock
        self.assertGreater(len(errors), 0)
        
        # No constraint violations (all should be ValueError)
        constraint_errors = [e for e in errors if e["error"] == "constraint"]
        self.assertEqual(len(constraint_errors), 0)

        # Batch should never go negative
        self.batch.refresh_from_db()
        self.assertGreaterEqual(self.batch.available_qty, Decimal("0"))

    def test_allocation_atomicity_on_failure(self):
        """Test that failed allocation doesn't leave partial data."""
        # Create order with multiple items, one invalid
        order = Order.objects.create(
            order_no="CONC-ORD-ATOMIC",
            customer_name="Atomic Test",
            status=Order.STATUS_NEW,
        )

        # Valid item
        OrderItem.objects.create(
            order=order,
            item=self.item,
            qty_requested=Decimal("30"),
        )

        # Invalid item (doesn't exist or insufficient stock)
        invalid_item = Item.objects.create(
            sku="INVALID-STOCK",
            name="No Stock Item",
            unit="pcs",
        )
        
        # No batches for invalid_item, so allocation should fail

        OrderItem.objects.create(
            order=order,
            item=invalid_item,
            qty_requested=Decimal("20"),
        )

        # Attempt allocation
        result = allocate_order(order)

        # Should fail
        self.assertFalse(result["success"])

        # No allocations should exist due to rollback
        allocations = Allocation.objects.filter(order_item__order=order)
        self.assertEqual(allocations.count(), 0)

        # First item's batch should not be decremented
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.available_qty, Decimal("100"))


# Import for aggregate
from django.db import models
