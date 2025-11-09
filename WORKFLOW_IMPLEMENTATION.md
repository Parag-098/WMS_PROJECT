# COMPLETE WORKFLOW IMPLEMENTATION - FILE TO FILE

## Overview
This document explains the complete order fulfillment workflow from allocation to delivery, showing exactly which files and functions are involved at each step.

---

## WORKFLOW STAGES

### **STAGE 1: ALLOCATE** ✅
**Purpose:** Reserve inventory from available batches using FEFO (First Expired First Out)

**Files Involved:**
1. **`inventory/urls.py`** (line 38)
   ```python
   path("order/<int:order_id>/allocate/", views.AllocateOrderView.as_view(), name="order-allocate")
   ```

2. **`inventory/views.py`** (lines 376-435) - `AllocateOrderView`
   - **GET:** Shows allocation confirmation page
   - **POST:** Calls `allocate_order()` service
   - **Redirects:** To order detail page
   - **Status Change:** `new` → `allocated`

3. **`inventory/services/allocation.py`** (lines 39-116) - `allocate_order()`
   - Creates **ManualQueue** of order items (FIFO)
   - For each item, calls `_allocate_item_with_stack()`
   - Updates order status to `STATUS_ALLOCATED`
   - Creates success/warning notifications

4. **`inventory/services/allocation.py`** (lines 119-226) - `_allocate_item_with_stack()`
   - Queries eligible batches sorted by expiry date
   - Creates **ManualStack** and pushes batches in REVERSE order
   - Pops stack to get earliest expiry first (FEFO)
   - Creates `Allocation` records
   - Reduces `Batch.available_qty` using F() expression
   - Logs transactions with `TransactionLog.TYPE_RESERVE`

5. **`inventory/services/structures.py`**
   - **ManualQueue** (lines 10-61): FIFO queue for order items
   - **ManualStack** (lines 64-111): LIFO stack for batch selection

**Database Changes:**
- `Order.status` = `allocated`
- `Allocation` records created
- `Batch.available_qty` reduced
- `TransactionLog` entries with TYPE_RESERVE
- `Notification` created

**Template:** `inventory/templates/inventory/allocate_confirm.html`

---

### **STAGE 2: PICK** ✅
**Purpose:** Physical picking from warehouse, confirm quantities

**Files Involved:**
1. **`inventory/urls.py`** (line 42)
   ```python
   path("order/<int:order_id>/pick/", views.PickView.as_view(), name="order-pick")
   ```

2. **`inventory/views.py`** (lines 540-642) - `PickView`
   - **GET:** Displays pick list with all allocations
   - **POST:** 
     - Processes `qty_picked_*` form fields
     - Logs discrepancies with `TransactionLog.TYPE_ADJUST`
     - Updates order status to `STATUS_PICKED`
   - **Status Change:** `allocated` → `picked`

**Database Changes:**
- `Order.status` = `picked`
- `TransactionLog` entries for pick adjustments (if any)

**Template:** `inventory/templates/inventory/pick.html`

**Form Fields:**
- `qty_picked_{allocation_id}` for each allocation

---

### **STAGE 3: PACK** ✅
**Purpose:** Pack items into boxes, confirm final quantities

**Files Involved:**
1. **`inventory/urls.py`** (line 43)
   ```python
   path("order/<int:order_id>/pack/", views.PackView.as_view(), name="order-pack")
   ```

2. **`inventory/views.py`** (lines 643-752) - `PackView`
   - **GET:** Shows packing form with order items
   - **POST:**
     - Processes `qty_packed_*` form fields
     - Updates `OrderItem.qty_picked`
     - Logs packing adjustments with `TransactionLog.TYPE_ADJUST`
     - Updates order status to `STATUS_PACKED`
   - **Status Change:** `picked` → `packed`

**Database Changes:**
- `Order.status` = `packed`
- `OrderItem.qty_picked` updated
- `TransactionLog` entries for pack adjustments (if any)

**Template:** `inventory/templates/inventory/pack.html`

**Form Fields:**
- `qty_packed_{order_item_id}` for each order item
- `notes_{order_item_id}` for adjustment notes

---

### **STAGE 4: SHIP** ✅
**Purpose:** Create shipment, generate tracking, finalize inventory consumption

**Files Involved:**
1. **`inventory/urls.py`** (line 44)
   ```python
   path("order/<int:order_id>/ship/", views.ShipView.as_view(), name="order-ship")
   ```

2. **`inventory/views.py`** (lines 755-880) - `ShipView`
   - **GET:** 
     - Validates order status (must be allocated/picked/packed)
     - Shows shipping form
   - **POST:**
     - Generates unique `tracking_no` (UUID)
     - Generates `shipment_no` format: `SHIP-{order_no}-{timestamp}`
     - Creates `Shipment` record
     - Logs consumption with `TransactionLog.TYPE_SHIP`
     - **Deletes allocations** (stock already deducted)
     - Checks low stock alerts
     - Updates order status to `STATUS_SHIPPED`
     - Sends notifications and webhooks
   - **Status Change:** `packed` → `shipped` (or `picked` → `shipped` if skipped)

**Database Changes:**
- `Order.status` = `shipped`
- `Shipment` record created with tracking number
- `Allocation` records deleted
- `TransactionLog` entries with TYPE_SHIP
- `Notification` created

**Template:** `inventory/templates/inventory/ship.html`

**Form Fields:**
- `carrier` (e.g., "FedEx", "UPS")
- `shipping_address`
- `notes`

**External Functions Called:**
- `send_low_stock_alert(item, qty)` - Email alert if below threshold
- `send_shipment_notification(shipment)` - Email to customer
- `webhook_shipment_created(shipment)` - External system webhook
- `webhook_order_fulfilled(order)` - Order completion webhook

---

### **STAGE 5: DELIVER** ✅
**Purpose:** Mark order as delivered to customer

**Files Involved:**
1. **`inventory/urls.py`** (line 45)
   ```python
   path("order/<int:order_id>/deliver/", views.DeliverView.as_view(), name="order-deliver")
   ```

2. **`inventory/views.py`** (lines 883-940) - `DeliverView`
   - **GET:** 
     - Validates order status (must be shipped)
     - Shows delivery confirmation form
   - **POST:**
     - Updates order status to `STATUS_DELIVERED`
     - Updates `Shipment.status` to delivered
     - Sets `Shipment.delivered_at` timestamp
     - Creates notification
   - **Status Change:** `shipped` → `delivered`

**Database Changes:**
- `Order.status` = `delivered`
- `Shipment.status` = `STATUS_DELIVERED`
- `Shipment.delivered_at` = current timestamp
- `Notification` created

**Template:** `inventory/templates/inventory/deliver.html`

---

## ALTERNATIVE FLOWS

### **Skip to Ship** (Staff Only)
**From:** `picked` status  
**To:** `shipped` status  
**Skips:** Pack step  
**Button:** Shows in `order_detail.html` when status = 'picked' and user is staff

---

## CANCELLATION FLOW

**Files Involved:**
1. **`inventory/urls.py`** (line 35)
   ```python
   path("orders/<int:pk>/cancel/", views.OrderCancelView.as_view(), name="order-cancel")
   ```

2. **`inventory/views.py`** - `OrderCancelView`
   - Deallocates all inventory
   - Returns stock to batches
   - Updates order status to `STATUS_CANCELLED`
   - Creates transaction logs for returns

**Available From:** Any status except `delivered` or `cancelled`

---

## DATA STRUCTURES USAGE

### **Queue (FIFO) - Order Item Processing**
**File:** `inventory/services/structures.py` (lines 10-61)

**Usage in allocation.py:**
```python
# Create queue
task_q: ManualQueue[OrderItem] = ManualQueue(max(16, len(order_items)))

# Enqueue all order items
for oi in order_items:
    task_q.enqueue(oi)

# Process in FIFO order
while not task_q.is_empty():
    order_item = task_q.dequeue()  # First in, first out
    result = _allocate_item_with_stack(order_item, user)
```

**Why Queue?** Ensures order items are processed in the sequence they were added.

---

### **Stack (LIFO) - Batch Selection (FEFO)**
**File:** `inventory/services/structures.py` (lines 64-111)

**Usage in allocation.py:**
```python
# Query batches sorted by expiry (earliest first)
eligible = Batch.objects.filter(...).order_by("expiry_date", "pk")

# Create stack
stack: ManualStack[int] = ManualStack(max(16, len(eligible)))

# Push in REVERSE order (last expiry first)
for row in reversed(eligible):
    stack.push(row["id"])

# Pop returns earliest expiry first (FEFO)
while (qty_remaining > 0) and (not stack.is_empty()):
    batch_id = stack.pop()  # Last in, first out (but reversed!)
    batch = Batch.objects.get(pk=batch_id)
    # Allocate from this batch
```

**Why Stack?** 
- Database returns: `[exp:2025-11-15, exp:2025-12-01, exp:2026-01-01]`
- Push reversed: Stack becomes `[2026-01-01, 2025-12-01, 2025-11-15]` (top)
- Pop returns: `2025-11-15` first → FEFO behavior!

---

## MODELS INVOLVED

### **Order** (`inventory/models.py`, lines 203-242)
**Status Flow:**
```
new → allocated → picked → packed → shipped → delivered
                                  ↓
                              cancelled (any time)
```

**Key Fields:**
- `order_no`: Unique identifier
- `status`: Current workflow stage
- `customer_name`: Customer info

---

### **OrderItem** (`inventory/models.py`, lines 244-310)
**Fields:**
- `order`: FK to Order
- `item`: FK to Item (SKU)
- `qty_requested`: What customer wants
- `qty_allocated`: What we reserved from batches
- `qty_picked`: What was actually picked (may differ)

---

### **Batch** (`inventory/models.py`, lines 73-173)
**Fields:**
- `item`: FK to Item
- `lot_no`: Auto-generated (LOT-YYYYMMDD-HHMMSS-XXXX)
- `quantity`: Total received
- `available_qty`: Current available (reduced during allocation)
- `expiry_date`: Used for FEFO sorting
- `status`: AVAILABLE, QUARANTINE, EXPIRED

---

### **Allocation** (`inventory/models.py`, lines 313-334)
**Purpose:** Links order items to specific batches

**Fields:**
- `order_item`: FK to OrderItem
- `batch`: FK to Batch
- `qty_allocated`: How much from this batch

**Lifecycle:**
- **Created:** During allocation (STAGE 1)
- **Used:** During pick/pack (STAGES 2-3)
- **Deleted:** During ship (STAGE 4) - stock already deducted

---

### **Shipment** (`inventory/models.py`, lines 337-370)
**Fields:**
- `order`: FK to Order
- `shipment_no`: SHIP-{order_no}-{timestamp}
- `tracking_no`: UUID for carrier tracking
- `carrier`: "FedEx", "UPS", etc.
- `shipped_at`: Timestamp
- `delivered_at`: Set in STAGE 5

---

### **TransactionLog** (`inventory/models.py`, lines 373-445)
**Purpose:** Audit trail of all inventory movements

**Transaction Types:**
- `TYPE_RECEIVE`: Stock received (batch creation)
- `TYPE_RESERVE`: Stock reserved (allocation)
- `TYPE_ADJUST`: Quantity adjustments (pick/pack discrepancies)
- `TYPE_SHIP`: Stock shipped (consumption)
- `TYPE_RETURN`: Customer returns

---

## TEMPLATES

### **Order Detail** (`inventory/templates/inventory/order_detail.html`)
**Workflow Buttons (lines 29-72):**
```django
{% if order.status == 'new' %}
    → Step 1: Allocate Stock

{% elif order.status == 'allocated' %}
    → Step 2: Pick Items
    → Deallocate (staff)

{% elif order.status == 'picked' %}
    → Step 3: Pack Items
    → Skip to Ship (staff)

{% elif order.status == 'packed' %}
    → Step 4: Ship Order

{% elif order.status == 'shipped' %}
    → Step 5: Mark as Delivered (staff)

{% elif order.status == 'delivered' %}
    → Order Completed badge

{% elif order.status == 'cancelled' %}
    → Order Cancelled badge
```

---

## COMPLETE FLOW EXAMPLE

### Scenario: Order #50 - Customer wants 100 Rice Sacks

**STAGE 1 - ALLOCATE:**
```
1. User clicks "Step 1: Allocate Stock"
2. URL: /order/50/allocate/
3. AllocateOrderView.post() called
4. allocate_order(50) service runs:
   - Queue: [Rice Order Item]
   - Dequeue: Rice Order Item
   - _allocate_item_with_stack():
     * Query: Batches for Rice, sorted by expiry
     * Result: [Batch#1 (exp: 2025-11-20, qty=60), Batch#2 (exp: 2025-12-15, qty=50)]
     * Stack push reversed: [Batch#2, Batch#1]
     * Pop: Batch#1 → allocate 60 units
     * Pop: Batch#2 → allocate 40 units (total 100)
   - Create 2 Allocation records
   - Reduce Batch#1.available_qty by 60
   - Reduce Batch#2.available_qty by 40
   - TransactionLog: 2 RESERVE entries
   - Order.status = 'allocated'
5. Redirect to order detail
6. Button shown: "Step 2: Pick Items"
```

**STAGE 2 - PICK:**
```
1. User clicks "Step 2: Pick Items"
2. URL: /order/50/pick/
3. PickView.get() shows pick list:
   - Allocation #1: Batch#1, pick 60
   - Allocation #2: Batch#2, pick 40
4. Warehouse picks, enters actual quantities
5. PickView.post() processes:
   - qty_picked_1 = 58 (short 2 units)
   - qty_picked_2 = 40 (exact)
   - TransactionLog: 1 ADJUST entry (2 units discrepancy)
   - Order.status = 'picked'
6. Redirect to order detail
7. Button shown: "Step 3: Pack Items"
```

**STAGE 3 - PACK:**
```
1. User clicks "Step 3: Pack Items"
2. URL: /order/50/pack/
3. PackView.get() shows pack form:
   - Order Item: Rice, allocated=98 (58+40)
4. User confirms 98 units packed
5. PackView.post() processes:
   - qty_packed_114 = 98
   - OrderItem.qty_picked = 98
   - Order.status = 'packed'
6. Redirect to order detail
7. Button shown: "Step 4: Ship Order"
```

**STAGE 4 - SHIP:**
```
1. User clicks "Step 4: Ship Order"
2. URL: /order/50/ship/
3. ShipView.get() shows shipping form
4. User enters:
   - carrier = "FedEx"
   - shipping_address = "123 Main St"
   - notes = "Handle with care"
5. ShipView.post() processes:
   - tracking_no = UUID generated
   - shipment_no = "SHIP-ORD-2024-050-20251109143022"
   - Create Shipment record
   - TransactionLog: 2 SHIP entries (Batch#1: -58, Batch#2: -40)
   - Delete 2 Allocation records
   - Check low stock: If Batch#1 or Batch#2 below threshold → alert
   - Order.status = 'shipped'
   - Send email notification
   - Trigger webhooks
6. Redirect to order detail
7. Button shown: "Step 5: Mark as Delivered"
```

**STAGE 5 - DELIVER:**
```
1. Customer receives package
2. Staff clicks "Step 5: Mark as Delivered"
3. URL: /order/50/deliver/
4. DeliverView.post() processes:
   - Order.status = 'delivered'
   - Shipment.status = 'delivered'
   - Shipment.delivered_at = NOW()
   - Notification created
5. Redirect to order detail
6. Badge shown: "Order Completed" ✅
```

---

## KEY DESIGN DECISIONS

### 1. **Why reduce Batch.available_qty during allocation, not shipping?**
- **Answer:** Prevents over-allocation. Once allocated, that stock is reserved and can't be allocated to another order.

### 2. **Why delete Allocations during shipping?**
- **Answer:** They're no longer needed. Stock already deducted, order is shipped, keeping them wastes space.

### 3. **Why use Queue + Stack instead of simple for loops?**
- **Answer:** 
  - Demonstrates data structure usage for coursework
  - Queue ensures FIFO order item processing
  - Stack enables FEFO (earliest expiry first) batch selection
  - Shows understanding of algorithm design

### 4. **Why allow partial allocation?**
- **Answer:** Real-world scenario - fulfill what's available, backorder the rest. Better than blocking entire order.

### 5. **Why separate Pick and Pack steps?**
- **Answer:**
  - **Pick:** Physical retrieval from shelves (may have discrepancies)
  - **Pack:** Final verification before boxing (catch errors)
  - Mimics real warehouse operations

---

## FILE SUMMARY

### Core Service Files:
- **`inventory/services/allocation.py`**: Order allocation logic with Queue + Stack
- **`inventory/services/structures.py`**: ManualQueue and ManualStack implementations

### View Files:
- **`inventory/views.py`**: All workflow views (Allocate, Pick, Pack, Ship, Deliver)

### Model Files:
- **`inventory/models.py`**: Order, OrderItem, Batch, Allocation, Shipment, TransactionLog

### URL Configuration:
- **`inventory/urls.py`**: Routes for all workflow endpoints

### Templates:
- **`inventory/templates/inventory/order_detail.html`**: Main order page with workflow buttons
- **`inventory/templates/inventory/allocate_confirm.html`**: Allocation confirmation
- **`inventory/templates/inventory/pick.html`**: Pick list
- **`inventory/templates/inventory/pack.html`**: Packing form
- **`inventory/templates/inventory/ship.html`**: Shipping form
- **`inventory/templates/inventory/deliver.html`**: Delivery confirmation
- **`inventory/templates/inventory/order_list.html`**: Order list with status filters

---

## DATABASE TRANSACTION FLOW

```sql
-- STAGE 1: ALLOCATE
BEGIN TRANSACTION;
  UPDATE inventory_batch SET available_qty = available_qty - 60 WHERE id = 1;  -- Batch#1
  UPDATE inventory_batch SET available_qty = available_qty - 40 WHERE id = 2;  -- Batch#2
  INSERT INTO inventory_allocation (order_item_id, batch_id, qty_allocated) VALUES (114, 1, 60);
  INSERT INTO inventory_allocation (order_item_id, batch_id, qty_allocated) VALUES (114, 2, 40);
  INSERT INTO inventory_transactionlog (type, qty, batch_id, ...) VALUES ('reserve', 60, 1, ...);
  INSERT INTO inventory_transactionlog (type, qty, batch_id, ...) VALUES ('reserve', 40, 2, ...);
  UPDATE inventory_order SET status = 'allocated' WHERE id = 50;
  INSERT INTO inventory_notification (...) VALUES (...);
COMMIT;

-- STAGE 2: PICK
BEGIN TRANSACTION;
  INSERT INTO inventory_transactionlog (type, qty, ...) VALUES ('adjust', -2, ...);  -- Discrepancy
  UPDATE inventory_order SET status = 'picked' WHERE id = 50;
COMMIT;

-- STAGE 3: PACK
BEGIN TRANSACTION;
  UPDATE inventory_orderitem SET qty_picked = 98 WHERE id = 114;
  UPDATE inventory_order SET status = 'packed' WHERE id = 50;
COMMIT;

-- STAGE 4: SHIP
BEGIN TRANSACTION;
  INSERT INTO inventory_shipment (...) VALUES (...);
  INSERT INTO inventory_transactionlog (type, qty, ...) VALUES ('ship', -58, ...);
  INSERT INTO inventory_transactionlog (type, qty, ...) VALUES ('ship', -40, ...);
  DELETE FROM inventory_allocation WHERE order_item_id IN (SELECT id FROM inventory_orderitem WHERE order_id = 50);
  UPDATE inventory_order SET status = 'shipped' WHERE id = 50;
  INSERT INTO inventory_notification (...) VALUES (...);
COMMIT;

-- STAGE 5: DELIVER
BEGIN TRANSACTION;
  UPDATE inventory_order SET status = 'delivered' WHERE id = 50;
  UPDATE inventory_shipment SET status = 'delivered', delivered_at = NOW() WHERE order_id = 50;
  INSERT INTO inventory_notification (...) VALUES (...);
COMMIT;
```

---

## ERROR HANDLING

### Allocation Errors:
- **OrderNotFoundError**: Order doesn't exist
- **AllocationError**: Generic allocation failure
- **InsufficientStockError**: Not enough inventory

### Validation Checks:
- **Pick**: Order must be 'allocated'
- **Pack**: Order must be 'picked'
- **Ship**: Order must be 'allocated', 'picked', or 'packed'
- **Deliver**: Order must be 'shipped'

### Transaction Rollback:
- All stages use `transaction.atomic()`
- If any error occurs, entire transaction rolls back
- Database remains consistent

---

## TESTING THE WORKFLOW

```bash
# 1. Create test order
python manage.py shell -c "
from inventory.models import Order, OrderItem, Item;
order = Order.objects.create(order_no='TEST-001', customer_name='Test Customer');
item = Item.objects.first();
OrderItem.objects.create(order=order, item=item, qty_requested=100);
print(f'Created order: {order.id}')
"

# 2. Test allocation
python manage.py shell -c "
from inventory.services.allocation import allocate_order;
from django.contrib.auth import get_user_model;
User = get_user_model();
user = User.objects.first();
result = allocate_order(ORDER_ID, user);
print(f'Allocation result: {result}')
"

# 3. Check order status
python manage.py shell -c "
from inventory.models import Order;
order = Order.objects.get(id=ORDER_ID);
print(f'Order status: {order.status}')
"
```

---

## CONCLUSION

This warehouse management system implements a complete order fulfillment workflow using:
- **Data Structures**: Queue (FIFO) for order processing, Stack (LIFO) for FEFO batch selection
- **Transaction Safety**: Atomic database operations
- **Audit Trail**: Complete transaction logging
- **Real-world Workflow**: Mirrors actual warehouse operations
- **Flexibility**: Allows staff to skip steps when needed

The implementation demonstrates understanding of:
- Algorithm design (FEFO using stack)
- Database transactions
- Django ORM and views
- RESTful URL design
- Template-driven UI
- Business logic separation (services layer)
