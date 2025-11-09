"""
Inventory domain models for the WMS project.

Migrations note:
Run after changes:
	python manage.py makemigrations inventory
	python manage.py migrate
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, Dict, Any

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone


# =============================
# Item and stock/batch handling
# =============================

class ItemQuerySet(models.QuerySet):
	"""Custom queryset for Item to provide stock-related annotations/filters."""

	def with_total_available(self):
		return self.annotate(total_available=Sum("batches__available_qty"))

	def low_stock(self):
		return self.with_total_available().filter(total_available__lte=F("reorder_threshold"))


class Item(models.Model):
	"""A sellable/stock-tracked item.

	Fields:
	  - sku: Unique SKU identifier for the item.
	  - name: Human-readable name.
	  - description: Optional description/details.
	  - unit: UoM string (e.g., pcs, kg, box).
	  - reorder_threshold: Quantity level at/below which the item should be reordered.
	  - price: Unit price for inventory valuation (added via migration).

	Helpers:
	  - total_quantity(): Returns the total available quantity across all non-expired batches.
	"""

	sku = models.CharField(max_length=64, unique=True)
	name = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	unit = models.CharField(max_length=16, default="pcs")
	reorder_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
	price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10.00"), help_text="Unit price for inventory valuation")

	objects = ItemQuerySet.as_manager()

	class Meta:
		ordering = ["sku"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"{self.sku} - {self.name}"

	def total_quantity(self) -> Decimal:
		"""Compute total available quantity across batches (ignoring expired/negative)."""
		total = self.batches.filter(
			models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gt=timezone.now().date())
		).aggregate(total=Sum("available_qty"))
		return total["total"] or Decimal("0")


class Batch(models.Model):
	"""A stock batch/lot for an Item.

	Fields:
	  - item: FK to Item.
	  - lot_no: Lot identifier (not guaranteed unique across items).
	  - received_qty: Quantity originally received in this batch.
	  - available_qty: Quantity currently available for allocation.
	  - expiry_date: Optional expiry/best-before date.
	  - status: State of the batch (AVAILABLE, RESERVED, HOLD, EXPIRED).

	Concurrency notes for reserve():
	  - Uses SELECT ... FOR UPDATE row locking to ensure the available_qty cannot
		be oversold under concurrent access.
	  - The method runs within a transaction.atomic() block and performs a
		select_for_update() fetch, then applies an F-expression decrement so the
		update is done database-side safely.

	Usage example:
		from django.db import transaction
		with transaction.atomic():
			new_available = batch.reserve(Decimal("3"))

	Returns the updated available quantity.
	Raises ValueError if insufficient stock or batch is not AVAILABLE.
	"""

	STATUS_AVAILABLE = "available"
	STATUS_RESERVED = "reserved"
	STATUS_HOLD = "hold"
	STATUS_EXPIRED = "expired"
	STATUS_CHOICES = [
		(STATUS_AVAILABLE, "Available"),
		(STATUS_RESERVED, "Reserved"),
		(STATUS_HOLD, "On Hold"),
		(STATUS_EXPIRED, "Expired"),
	]

	item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="batches")
	lot_no = models.CharField(max_length=64)
	received_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
	available_qty = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
	expiry_date = models.DateField(null=True, blank=True)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)

	class Meta:
		ordering = ["item__sku", "lot_no"]
		constraints = [
			models.CheckConstraint(check=models.Q(available_qty__gte=0), name="batch_available_nonneg"),
			models.UniqueConstraint(fields=["item", "lot_no"], name="uniq_item_lot"),
		]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Batch({self.item.sku} #{self.lot_no})"

	def reserve(self, qty: Decimal) -> Decimal:
		"""Reserve qty units from this batch with DB-level locking.

		- Ensures the row is locked using SELECT FOR UPDATE to prevent races.
		- Uses an F-expression to atomically decrement available_qty.
		- Raises ValueError if the batch is not AVAILABLE or insufficient stock.

		Returns the new available quantity.
		"""
		if Decimal(qty) <= 0:
			raise ValueError("Reserve quantity must be > 0")

		with transaction.atomic():
			locked = Batch.objects.select_for_update().get(pk=self.pk)
			if locked.status != Batch.STATUS_AVAILABLE:
				raise ValueError("Batch is not in AVAILABLE status")
			if locked.available_qty < qty:
				raise ValueError("Insufficient quantity in batch")

			Batch.objects.filter(pk=locked.pk).update(available_qty=F("available_qty") - qty)
			locked.refresh_from_db(fields=["available_qty"])
			return locked.available_qty


# =============================
# Orders, allocations, shipments
# =============================

class Order(models.Model):
	"""A customer order.

	Fields:
	  - order_no: Business unique order number.
	  - customer_name: Optional free-text customer name.
	  - status: NEW, ALLOCATED, SHIPPED, CANCELLED
	"""

	STATUS_NEW = "new"
	STATUS_ALLOCATED = "allocated"
	STATUS_PICKED = "picked"
	STATUS_SHIPPED = "shipped"
	STATUS_DELIVERED = "delivered"
	STATUS_CANCELLED = "cancelled"
	STATUS_CHOICES = [
		(STATUS_NEW, "New"),
		(STATUS_ALLOCATED, "Allocated"),
		(STATUS_PICKED, "Picked"),
		(STATUS_SHIPPED, "Shipped"),
		(STATUS_DELIVERED, "Delivered"),
		(STATUS_CANCELLED, "Cancelled"),
	]

	order_no = models.CharField(max_length=64, unique=True)
	customer_name = models.CharField(max_length=255, blank=True)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Order {self.order_no}"

	def save(self, *args, **kwargs):
		"""Auto-generate order_no if not provided."""
		if not self.order_no:
			# Generate order number in format: ORD-YYYYMMDD-NNNN
			from django.utils import timezone
			today = timezone.now().strftime('%Y%m%d')
			
			# Find the last order number for today
			last_order = Order.objects.filter(
				order_no__startswith=f'ORD-{today}-'
			).order_by('-order_no').first()
			
			if last_order:
				# Extract the sequence number and increment
				try:
					last_seq = int(last_order.order_no.split('-')[-1])
					new_seq = last_seq + 1
				except (ValueError, IndexError):
					new_seq = 1
			else:
				new_seq = 1
			
			self.order_no = f'ORD-{today}-{new_seq:04d}'
		
		super().save(*args, **kwargs)

	@property
	def is_fully_allocated(self) -> bool:
		items = self.items.all()
		if not items.exists():
			return False
		return all(i.qty_allocated >= i.qty_requested for i in items)


class OrderItem(models.Model):
	"""Line item on an Order.

	Fields:
	  - order: FK to Order
	  - item: FK to Item
	  - qty_requested: Desired quantity
	  - qty_allocated: Quantity allocated so far

	Helpers:
	  - allocate_from_batch(batch, qty): Reserves from batch and records an Allocation.
	"""

	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="order_lines")
	qty_requested = models.DecimalField(max_digits=12, decimal_places=3)
	qty_allocated = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["order", "item"], name="uniq_order_item"),
			models.CheckConstraint(check=models.Q(qty_requested__gt=0), name="qty_requested_gt_zero"),
			models.CheckConstraint(check=models.Q(qty_allocated__gte=0), name="qty_allocated_nonneg"),
		]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"{self.order.order_no} - {self.item.sku}"

	def allocate_from_batch(self, batch: Batch, qty: Decimal) -> "Allocation":
		"""Reserve stock from a batch and create an Allocation entry.

		Performs a batch.reserve(qty) under an atomic transaction and increments
		this line's qty_allocated. Returns the created Allocation.
		"""
		if batch.item_id != self.item_id:
			raise ValueError("Batch item mismatch")

		with transaction.atomic():
			batch.reserve(qty)
			Allocation.objects.create(order_item=self, batch=batch, qty_allocated=qty)
			OrderItem.objects.filter(pk=self.pk).update(qty_allocated=F("qty_allocated") + qty)
			self.refresh_from_db(fields=["qty_allocated"])
			return self.allocations.latest("created_at")


class Allocation(models.Model):
	"""Allocation links an OrderItem to a specific Batch and reserved quantity."""

	order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="allocations")
	batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="allocations")
	qty_allocated = models.DecimalField(max_digits=12, decimal_places=3)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Alloc {self.order_item.order.order_no}:{self.order_item.item.sku} -> {self.batch.lot_no} ({self.qty_allocated})"


class Shipment(models.Model):
	"""Represents a shipment for an Order.

	Fields:
	  - shipment_no: Business unique shipment number.
	  - order: FK to the Order being shipped.
	  - tracking_no: UUID tracking identifier.
	  - status: CREATED, IN_TRANSIT, DELIVERED, CANCELLED
	  - carrier: Shipping carrier name (e.g., FedEx, UPS).
	  - shipping_address: Full shipping address.
	  - notes: Optional shipment notes.
	  - created_at: Creation timestamp.
	  - shipped_at: When the shipment was dispatched.
	  - delivered_at: When the shipment was delivered.
	"""

	STATUS_CREATED = "created"
	STATUS_IN_TRANSIT = "in_transit"
	STATUS_DELIVERED = "delivered"
	STATUS_CANCELLED = "cancelled"
	STATUS_CHOICES = [
		(STATUS_CREATED, "Created"),
		(STATUS_IN_TRANSIT, "In Transit"),
		(STATUS_DELIVERED, "Delivered"),
		(STATUS_CANCELLED, "Cancelled"),
	]

	shipment_no = models.CharField(max_length=64, unique=True)
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
	tracking_no = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
	carrier = models.CharField(max_length=128, blank=True)
	shipping_address = models.TextField(blank=True)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	shipped_at = models.DateTimeField(null=True, blank=True)
	delivered_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Shipment {self.shipment_no} for {self.order.order_no}"


class Return(models.Model):
	"""RMA (Return Merchandise Authorization) for returned items.
	
	Fields:
	  - return_no: Unique return identifier.
	  - order_item: FK to the OrderItem being returned.
	  - qty_returned: Quantity being returned.
	  - reason: Return reason (damaged, wrong_item, defective, customer_change, other).
	  - status: pending, inspected, restocked, scrapped, quarantined
	  - created_at: Creation timestamp.
	  - processed_at: Processing timestamp.
	  - notes: Optional processing notes.
	"""
	
	REASON_DAMAGED = "damaged"
	REASON_WRONG_ITEM = "wrong_item"
	REASON_DEFECTIVE = "defective"
	REASON_CUSTOMER_CHANGE = "customer_change"
	REASON_OTHER = "other"
	REASON_CHOICES = [
		(REASON_DAMAGED, "Damaged"),
		(REASON_WRONG_ITEM, "Wrong Item"),
		(REASON_DEFECTIVE, "Defective"),
		(REASON_CUSTOMER_CHANGE, "Customer Change"),
		(REASON_OTHER, "Other"),
	]
	
	STATUS_PENDING = "pending"
	STATUS_INSPECTED = "inspected"
	STATUS_RESTOCKED = "restocked"
	STATUS_SCRAPPED = "scrapped"
	STATUS_QUARANTINED = "quarantined"
	STATUS_CHOICES = [
		(STATUS_PENDING, "Pending Inspection"),
		(STATUS_INSPECTED, "Inspected"),
		(STATUS_RESTOCKED, "Restocked"),
		(STATUS_SCRAPPED, "Scrapped"),
		(STATUS_QUARANTINED, "Quarantined"),
	]
	
	return_no = models.CharField(max_length=64, unique=True)
	order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="returns")
	qty_returned = models.DecimalField(max_digits=12, decimal_places=3)
	reason = models.CharField(max_length=32, choices=REASON_CHOICES)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	processed_at = models.DateTimeField(null=True, blank=True)
	notes = models.TextField(blank=True)
	
	class Meta:
		ordering = ["-created_at"]
	
	def __str__(self) -> str:
		return f"Return {self.return_no} - {self.order_item.item.sku} ({self.qty_returned})"


# =============================
# Auditing, notifications, stacks
# =============================

class TransactionLog(models.Model):
	"""Immutable ledger of stock-affecting operations.

	Fields:
	  - user: Optional FK to the actor (auth user).
	  - type: Operation type (RECEIPT, RESERVE, RELEASE, SHIP, ADJUST).
	  - qty: Quantity impacted (positive or negative by convention).
	  - item, batch, order, shipment: Optional references for context.
	  - timestamp: Creation time.

	Immutability:
	  - Records cannot be updated after creation. Attempts to save() an existing
		record raise a ValueError.
	"""

	TYPE_RECEIPT = "receipt"
	TYPE_RESERVE = "reserve"
	TYPE_RELEASE = "release"
	TYPE_DEALLOCATE = "deallocate"
	TYPE_SHIP = "ship"
	TYPE_ADJUST = "adjust"
	TYPE_CHOICES = [
		(TYPE_RECEIPT, "Receipt"),
		(TYPE_RESERVE, "Reserve"),
		(TYPE_RELEASE, "Release"),
		(TYPE_DEALLOCATE, "Deallocate"),
		(TYPE_SHIP, "Ship"),
		(TYPE_ADJUST, "Adjust"),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	type = models.CharField(max_length=16, choices=TYPE_CHOICES)
	qty = models.DecimalField(max_digits=12, decimal_places=3)

	item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
	batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True)
	order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
	shipment = models.ForeignKey(Shipment, on_delete=models.SET_NULL, null=True, blank=True)

	timestamp = models.DateTimeField(auto_now_add=True)
	meta = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["-timestamp"]
		indexes = [models.Index(fields=["type", "timestamp"])]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Txn[{self.type}] qty={self.qty} at {self.timestamp:%Y-%m-%d %H:%M:%S}"

	def save(self, *args, **kwargs):
		if self.pk:
			raise ValueError("TransactionLog records are immutable and cannot be updated")
		return super().save(*args, **kwargs)


class Notification(models.Model):
	"""System/user notification.

	Fields:
	  - user: Optional target user (nullable for broadcast/system messages).
	  - message: Notification text.
	  - level: INFO, WARNING, ERROR.
	  - is_read: Whether the notification has been read.
	  - created_at: Timestamp.
	"""

	LEVEL_INFO = "info"
	LEVEL_WARNING = "warning"
	LEVEL_ERROR = "error"
	LEVEL_CHOICES = [
		(LEVEL_INFO, "Info"),
		(LEVEL_WARNING, "Warning"),
		(LEVEL_ERROR, "Error"),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	message = models.TextField()
	level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_INFO)
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		prefix = self.level.upper()
		return f"{prefix}: {self.message[:40]}..."

	def mark_read(self):
		self.is_read = True
		self.save(update_fields=["is_read"])


class UndoStack(models.Model):
	"""DB-backed LIFO stack for reversible operations (undo).

	Provides push()/pop() helpers that operate under a DB transaction and select_for_update()
	to coordinate concurrent access.
	"""

	op_name = models.CharField(max_length=128)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at", "-id"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Undo({self.op_name}) at {self.created_at:%H:%M:%S}"

	@classmethod
	def push(cls, op_name: str, metadata: Optional[Dict[str, Any]] = None) -> "UndoStack":
		return cls.objects.create(op_name=op_name, metadata=metadata or {})

	@classmethod
	def pop(cls) -> Optional["UndoStack"]:
		with transaction.atomic():
			top = cls.objects.select_for_update().order_by("-id").first()
			if not top:
				return None
			# Make a copy to return after deletion (so callers still have data)
			data = {"op_name": top.op_name, "metadata": top.metadata, "created_at": top.created_at}
			top.delete()
			inst = cls(op_name=data["op_name"], metadata=data["metadata"])  # unsaved copy for convenience
			inst.created_at = data["created_at"]
			return inst


class RedoStack(models.Model):
	"""DB-backed LIFO stack for redo operations complementary to UndoStack."""

	op_name = models.CharField(max_length=128)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at", "-id"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Redo({self.op_name}) at {self.created_at:%H:%M:%S}"

	@classmethod
	def push(cls, op_name: str, metadata: Optional[Dict[str, Any]] = None) -> "RedoStack":
		return cls.objects.create(op_name=op_name, metadata=metadata or {})

	@classmethod
	def pop(cls) -> Optional["RedoStack"]:
		with transaction.atomic():
			top = cls.objects.select_for_update().order_by("-id").first()
			if not top:
				return None
			data = {"op_name": top.op_name, "metadata": top.metadata, "created_at": top.created_at}
			top.delete()
			inst = cls(op_name=data["op_name"], metadata=data["metadata"])  # unsaved copy
			inst.created_at = data["created_at"]
			return inst


# =============================
# Graph models for network view
# =============================

class GraphNode(models.Model):
	"""A node within the warehouse/delivery network.

	Fields:
	  - key: Unique node key (used for graph refs and Cytoscape id).
	  - label: Human label.
	  - group: Optional grouping/category.
	  - pos_x, pos_y: Optional layout coordinates.
	  - data: Arbitrary JSON metadata.

	Helper:
	  - to_cytoscape(): Returns an element dict suitable for Cytoscape.js.
	"""

	key = models.CharField(max_length=64, unique=True)
	label = models.CharField(max_length=255)
	group = models.CharField(max_length=64, blank=True)
	pos_x = models.FloatField(default=0)
	pos_y = models.FloatField(default=0)
	data = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["key"]

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Node({self.key}) {self.label}"

	def to_cytoscape(self) -> Dict[str, Any]:
		return {
			"group": "nodes",
			"data": {"id": self.key, "label": self.label, **(self.data or {})},
			"position": {"x": self.pos_x, "y": self.pos_y},
		}


class GraphEdge(models.Model):
	"""An edge between GraphNodes.

	Fields:
	  - source, target: FKs to GraphNode
	  - label: Optional label
	  - weight: Numeric weight/cost
	  - directed: Whether this edge is directed
	  - data: Arbitrary JSON metadata

	Helper:
	  - to_cytoscape(): Returns an element dict suitable for Cytoscape.js.
	"""

	source = models.ForeignKey(GraphNode, on_delete=models.CASCADE, related_name="out_edges")
	target = models.ForeignKey(GraphNode, on_delete=models.CASCADE, related_name="in_edges")
	label = models.CharField(max_length=255, blank=True)
	weight = models.FloatField(default=1.0)
	directed = models.BooleanField(default=True)
	data = models.JSONField(default=dict, blank=True)

	class Meta:
		ordering = ["source__key", "target__key"]
		constraints = [
			models.UniqueConstraint(fields=["source", "target", "label", "directed"], name="uniq_edge"),
		]

	def __str__(self) -> str:  # pragma: no cover - trivial
		arrow = "->" if self.directed else "--"
		return f"{self.source.key} {arrow} {self.target.key} ({self.label})"

	def to_cytoscape(self) -> Dict[str, Any]:
		edge_id = f"{self.source.key}:{self.target.key}:{self.pk or 'new'}"
		payload = {"id": edge_id, "source": self.source.key, "target": self.target.key}
		if self.label:
			payload["label"] = self.label
		payload["weight"] = self.weight
		payload.update(self.data or {})
		return {"group": "edges", "data": payload}
