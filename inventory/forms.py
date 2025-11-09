"""
Forms for the inventory app with validation logic.
"""
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Item, Batch, Order, OrderItem, Return




class ItemForm(forms.ModelForm):
    """Form for creating/updating Items with SKU uniqueness validation."""

    class Meta:
        model = Item
        fields = ["sku", "name", "description", "unit", "reorder_threshold"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get("sku", "").strip().upper()
        if not sku:
            raise ValidationError("SKU is required.")

        # Check uniqueness (excluding current instance if editing)
        qs = Item.objects.filter(sku=sku)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Item with SKU '{sku}' already exists.")

        return sku

    def clean_reorder_threshold(self):
        threshold = self.cleaned_data.get("reorder_threshold")
        if threshold is not None and threshold < Decimal("0"):
            raise ValidationError("Reorder threshold cannot be negative.")
        return threshold


class BatchForm(forms.ModelForm):
    """Form for creating/updating Batches with expiry and quantity validation."""

    class Meta:
        model = Batch
        fields = ["item", "lot_no", "received_qty", "available_qty", "expiry_date", "status"]
        widgets = {
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_expiry_date(self):
        expiry = self.cleaned_data.get("expiry_date")
        if expiry and expiry < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry

    def clean_received_qty(self):
        qty = self.cleaned_data.get("received_qty")
        if qty is not None and qty <= Decimal("0"):
            raise ValidationError("Received quantity must be positive.")
        return qty

    def clean_available_qty(self):
        qty = self.cleaned_data.get("available_qty")
        if qty is not None and qty < Decimal("0"):
            raise ValidationError("Available quantity cannot be negative.")
        return qty

    def clean(self):
        cleaned_data = super().clean()
        received = cleaned_data.get("received_qty")
        available = cleaned_data.get("available_qty")

        if received is not None and available is not None:
            if available > received:
                raise ValidationError("Available quantity cannot exceed received quantity.")

        return cleaned_data


class OrderForm(forms.ModelForm):
    """Form for creating/updating Orders."""

    class Meta:
        model = Order
        fields = ["order_no", "customer_name", "status"]
        widgets = {
            "order_no": forms.TextInput(attrs={
                "placeholder": "Auto-generated if left blank",
                "class": "form-control"
            }),
            "customer_name": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make order_no optional for creation
        self.fields["order_no"].required = False

    def clean_order_no(self):
        order_no = self.cleaned_data.get("order_no", "").strip()
        
        # If blank, it will be auto-generated
        if not order_no:
            return ""

        # Check uniqueness (excluding current instance if editing)
        qs = Order.objects.filter(order_no=order_no)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Order '{order_no}' already exists.")

        return order_no


class OrderItemForm(forms.ModelForm):
    """Form for creating/updating OrderItems (line items)."""

    class Meta:
        model = OrderItem
        fields = ["item", "qty_requested"]

    def clean_qty_requested(self):
        qty = self.cleaned_data.get("qty_requested")
        if qty is not None and qty <= Decimal("0"):
            raise ValidationError("Requested quantity must be positive.")
        return qty


class BaseOrderItemInlineFormSet(forms.BaseInlineFormSet):
    """Base inline formset for OrderItems with extra validation."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        items = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                item = form.cleaned_data.get("item")
                if item:
                    if item in items:
                        raise ValidationError(f"Duplicate item '{item.sku}' in order.")
                    items.append(item)

        if not items:
            raise ValidationError("Order must contain at least one item.")


# Create the actual formset using inlineformset_factory
OrderItemInlineFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    formset=BaseOrderItemInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ReceiveForm(forms.Form):
    """Bulk form for receiving batches of items.
    
    Allows creating multiple batches at once for stock receipt operations.
    """

    item = forms.ModelChoiceField(
        queryset=Item.objects.all(),
        required=True,
        label="Item",
        help_text="Select the item to receive.",
    )
    lot_no = forms.CharField(
        max_length=64,
        required=True,
        label="Lot Number",
        help_text="Unique lot/batch identifier.",
    )
    received_qty = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=True,
        label="Received Quantity",
        help_text="Quantity received in this batch.",
    )
    expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Expiry Date",
        help_text="Optional expiry or best-before date.",
    )

    def clean_received_qty(self):
        qty = self.cleaned_data.get("received_qty")
        if qty is not None and qty <= Decimal("0"):
            raise ValidationError("Received quantity must be positive.")
        return qty

    def clean_expiry_date(self):
        expiry = self.cleaned_data.get("expiry_date")
        if expiry and expiry < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get("item")
        lot_no = cleaned_data.get("lot_no")

        # Check if this lot already exists for the item
        if item and lot_no:
            if Batch.objects.filter(item=item, lot_no=lot_no).exists():
                raise ValidationError(f"Batch with lot '{lot_no}' already exists for item '{item.sku}'.")

        return cleaned_data

    def save(self):
        """Create and return a new Batch instance from the form data."""
        item = self.cleaned_data["item"]
        lot_no = self.cleaned_data["lot_no"]
        received_qty = self.cleaned_data["received_qty"]
        expiry_date = self.cleaned_data.get("expiry_date")

        batch = Batch.objects.create(
            item=item,
            lot_no=lot_no,
            received_qty=received_qty,
            available_qty=received_qty,  # Initially all received qty is available
            expiry_date=expiry_date,
            status=Batch.STATUS_AVAILABLE,
        )
        return batch


# =============================
# Pick, Pack, Ship Forms
# =============================

class PickForm(forms.Form):
    """Form for confirming picked quantities against allocations."""
    
    allocation_id = forms.IntegerField(widget=forms.HiddenInput())
    qty_picked = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=True,
        label="Quantity Picked",
        help_text="Actual quantity picked from warehouse.",
    )
    
    def clean_qty_picked(self):
        qty = self.cleaned_data.get("qty_picked")
        if qty is not None and qty < Decimal("0"):
            raise ValidationError("Picked quantity cannot be negative.")
        return qty


class PackForm(forms.Form):
    """Form for confirming packing and optionally adjusting quantities."""
    
    order_item_id = forms.IntegerField(widget=forms.HiddenInput())
    qty_packed = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=True,
        label="Quantity Packed",
        help_text="Final quantity packed for shipment.",
    )
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Packing Notes",
        help_text="Optional notes about packing adjustments.",
    )
    
    def clean_qty_packed(self):
        qty = self.cleaned_data.get("qty_packed")
        if qty is not None and qty < Decimal("0"):
            raise ValidationError("Packed quantity cannot be negative.")
        return qty


class ShipForm(forms.Form):
    """Form for creating shipment with tracking number."""
    
    order_id = forms.IntegerField(widget=forms.HiddenInput())
    carrier = forms.CharField(
        max_length=100,
        required=False,
        label="Carrier",
        help_text="Shipping carrier (e.g., FedEx, UPS, DHL).",
    )
    shipping_address = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Shipping Address",
    )
    notes = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Shipment Notes",
    )
    
    def clean_shipping_address(self):
        address = self.cleaned_data.get("shipping_address", "").strip()
        if not address:
            raise ValidationError("Shipping address is required.")
        return address


# =============================
# RMA (Return) Forms
# =============================

class ReturnForm(forms.ModelForm):
    """Form for creating a return tied to an OrderItem."""
    
    class Meta:
        model = Return
        fields = ["order_item", "qty_returned", "reason", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
    
    def clean_qty_returned(self):
        qty = self.cleaned_data.get("qty_returned")
        if qty is not None and qty <= Decimal("0"):
            raise ValidationError("Return quantity must be positive.")
        return qty
    
    def clean(self):
        cleaned_data = super().clean()
        order_item = cleaned_data.get("order_item")
        qty_returned = cleaned_data.get("qty_returned")
        
        if order_item and qty_returned:
            # Validate quantity doesn't exceed what was shipped
            if qty_returned > order_item.qty_requested:
                raise ValidationError(
                    f"Return quantity ({qty_returned}) cannot exceed ordered quantity ({order_item.qty_requested})."
                )
        
        return cleaned_data


class ReturnProcessForm(forms.Form):
    """Form for processing a return with restock options."""
    
    DISPOSITION_RESTOCK_ORIGINAL = "restock_original"
    DISPOSITION_RESTOCK_NEW = "restock_new"
    DISPOSITION_QUARANTINE = "quarantine"
    DISPOSITION_SCRAP = "scrap"
    
    DISPOSITION_CHOICES = [
        (DISPOSITION_RESTOCK_ORIGINAL, "Restock to Original Batch"),
        (DISPOSITION_RESTOCK_NEW, "Create New Return Batch"),
        (DISPOSITION_QUARANTINE, "Quarantine for Inspection"),
        (DISPOSITION_SCRAP, "Scrap/Discard"),
    ]
    
    return_id = forms.IntegerField(widget=forms.HiddenInput())
    disposition = forms.ChoiceField(
        choices=DISPOSITION_CHOICES,
        required=True,
        label="Disposition",
        help_text="How to handle the returned items.",
    )
    qty_accepted = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=True,
        label="Quantity Accepted",
        help_text="Quantity accepted back into inventory (if restocking).",
    )
    notes = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Processing Notes",
    )
    
    def clean_qty_accepted(self):
        qty = self.cleaned_data.get("qty_accepted")
        if qty is not None and qty < Decimal("0"):
            raise ValidationError("Accepted quantity cannot be negative.")
        return qty


# =============================
# Bulk Import Form
# =============================

class BulkImportForm(forms.Form):
    """Form for uploading bulk import files."""
    
    file = forms.FileField(
        label="Upload File",
        help_text="Upload CSV or XLSX file for bulk import",
        required=True,
    )
    
    model_type = forms.ChoiceField(
        choices=[
            ("item", "Items"),
            ("batch", "Batches"),
            ("order", "Orders"),
        ],
        label="Import Type",
        required=True,
    )
    
    def clean_file(self):
        file = self.cleaned_data.get("file")
        
        if not file:
            raise ValidationError("No file uploaded")
        
        # Validate file extension
        allowed_extensions = ['.csv', '.xlsx', '.xls']
        file_name = file.name.lower()
        
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise ValidationError(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            raise ValidationError(
                f"File too large. Maximum size: 10MB"
            )
        
        return file
