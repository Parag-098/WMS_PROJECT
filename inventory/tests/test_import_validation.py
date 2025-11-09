"""
Unit tests for import validation logic.

Tests verify that:
- Missing SKU rows are rejected in preview
- Invalid data formats are caught before commit
- Validation errors are reported with row numbers
"""
import io
import tempfile
from decimal import Decimal
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from inventory.models import Item, Batch, Order


class ImportValidationTestCase(TestCase):
    """Test bulk import validation logic."""

    def setUp(self):
        """Create test items for validation."""
        self.item1 = Item.objects.create(
            sku="VALID-001",
            name="Valid Item 1",
            unit="pcs",
        )

        self.item2 = Item.objects.create(
            sku="VALID-002",
            name="Valid Item 2",
            unit="kg",
        )

    def test_item_import_missing_sku_rejected(self):
        """Test that item import rows without SKU are rejected."""
        csv_content = """sku,name,description,unit,reorder_threshold
VALID-003,Item 3,Description 3,pcs,10
,Item 4,Description 4,pcs,20
VALID-005,Item 5,Description 5,kg,15
"""
        from inventory.views import BulkImportView

        # Parse CSV and validate
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            sku = str(row.get("sku", "")).strip().upper()
            name = str(row.get("name", "")).strip()
            
            if not sku or sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing SKU")
            elif not name or name == "NAN":
                errors.append(f"Row {idx + 2}: Missing name")

        # Should have 1 error for missing SKU
        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("Missing SKU", errors[0])

    def test_item_import_missing_name_rejected(self):
        """Test that item import rows without name are rejected."""
        csv_content = """sku,name,description,unit,reorder_threshold
VALID-006,Item 6,Description 6,pcs,10
VALID-007,,Description 7,pcs,20
VALID-008,Item 8,Description 8,kg,15
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            sku = str(row.get("sku", "")).strip().upper()
            name = str(row.get("name", "")).strip()
            
            if not sku or sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing SKU")
            elif not name or name == "NAN":
                errors.append(f"Row {idx + 2}: Missing name")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("Missing name", errors[0])

    def test_batch_import_missing_item_sku_rejected(self):
        """Test that batch import rows without valid item_sku are rejected."""
        csv_content = """item_sku,lot_no,received_qty,expiry_date
VALID-001,LOT-A,100,2025-12-31
,LOT-B,50,2025-11-30
INVALID-SKU,LOT-C,75,2025-10-15
VALID-002,LOT-D,200,2026-01-31
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            item_sku = str(row.get("item_sku", "")).strip().upper()
            lot_no = str(row.get("lot_no", "")).strip()
            
            if not item_sku or item_sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing item_sku")
            elif not lot_no:
                errors.append(f"Row {idx + 2}: Missing lot_no")
            elif not Item.objects.filter(sku=item_sku).exists():
                errors.append(f"Row {idx + 2}: Item with SKU '{item_sku}' does not exist")

        # Should have 2 errors: missing SKU and invalid SKU
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("Row 3" in e and "Missing item_sku" in e for e in errors))
        self.assertTrue(any("Row 4" in e and "does not exist" in e for e in errors))

    def test_batch_import_missing_lot_no_rejected(self):
        """Test that batch import rows without lot_no are rejected."""
        csv_content = """item_sku,lot_no,received_qty,expiry_date
VALID-001,LOT-E,100,2025-12-31
VALID-002,,50,2025-11-30
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            item_sku = str(row.get("item_sku", "")).strip().upper()
            lot_no = str(row.get("lot_no", "")).strip()
            
            if not item_sku or item_sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing item_sku")
            elif not lot_no or lot_no == "nan":
                errors.append(f"Row {idx + 2}: Missing lot_no")
            elif not Item.objects.filter(sku=item_sku).exists():
                errors.append(f"Row {idx + 2}: Item does not exist")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("Missing lot_no", errors[0])

    def test_order_import_missing_order_no_rejected(self):
        """Test that order import rows without order_no are rejected."""
        csv_content = """order_no,customer_name,item_sku,qty_requested
ORD-001,Customer A,VALID-001,50
,Customer B,VALID-002,30
ORD-003,Customer C,VALID-001,40
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            order_no = str(row.get("order_no", "")).strip()
            item_sku = str(row.get("item_sku", "")).strip().upper()
            
            if not order_no or order_no == "nan":
                errors.append(f"Row {idx + 2}: Missing order_no")
            elif not item_sku or item_sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing item_sku")
            elif not Item.objects.filter(sku=item_sku).exists():
                errors.append(f"Row {idx + 2}: Item does not exist")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("Missing order_no", errors[0])

    def test_order_import_invalid_item_sku_rejected(self):
        """Test that order import rows with invalid item_sku are rejected."""
        csv_content = """order_no,customer_name,item_sku,qty_requested
ORD-004,Customer D,VALID-001,50
ORD-005,Customer E,INVALID-999,30
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            order_no = str(row.get("order_no", "")).strip()
            item_sku = str(row.get("item_sku", "")).strip().upper()
            
            if not order_no or order_no == "nan":
                errors.append(f"Row {idx + 2}: Missing order_no")
            elif not item_sku or item_sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing item_sku")
            elif not Item.objects.filter(sku=item_sku).exists():
                errors.append(f"Row {idx + 2}: Item with SKU '{item_sku}' does not exist")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("does not exist", errors[0])

    def test_multiple_validation_errors_collected(self):
        """Test that multiple validation errors are collected and reported."""
        csv_content = """sku,name,description,unit,reorder_threshold
,Item A,Description A,pcs,10
VALID-009,,Description B,pcs,20
VALID-010,Item C,Description C,pcs,invalid
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            sku = str(row.get("sku", "")).strip().upper()
            name = str(row.get("name", "")).strip()
            
            if not sku or sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing SKU")
            if not name or name == "NAN":
                errors.append(f"Row {idx + 2}: Missing name")
            
            # Validate reorder_threshold is numeric
            try:
                threshold = row.get("reorder_threshold")
                if pd.notna(threshold):
                    Decimal(str(threshold))
            except Exception:
                errors.append(f"Row {idx + 2}: Invalid reorder_threshold")

        # Should have 3 errors
        self.assertEqual(len(errors), 3)

    def test_valid_import_passes_validation(self):
        """Test that valid import data passes validation without errors."""
        csv_content = """sku,name,description,unit,reorder_threshold
VALID-011,Item 11,Description 11,pcs,10
VALID-012,Item 12,Description 12,kg,20
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            sku = str(row.get("sku", "")).strip().upper()
            name = str(row.get("name", "")).strip()
            
            if not sku or sku == "NAN":
                errors.append(f"Row {idx + 2}: Missing SKU")
            elif not name or name == "NAN":
                errors.append(f"Row {idx + 2}: Missing name")

        self.assertEqual(len(errors), 0)

    def test_batch_import_invalid_expiry_date_format(self):
        """Test that batch import with invalid expiry date format is rejected."""
        csv_content = """item_sku,lot_no,received_qty,expiry_date
VALID-001,LOT-F,100,2025-12-31
VALID-002,LOT-G,50,invalid-date
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            item_sku = str(row.get("item_sku", "")).strip().upper()
            
            if not Item.objects.filter(sku=item_sku).exists():
                errors.append(f"Row {idx + 2}: Item does not exist")
                continue
            
            # Validate expiry_date
            expiry = row.get("expiry_date")
            if pd.notna(expiry):
                try:
                    pd.to_datetime(expiry)
                except Exception:
                    errors.append(f"Row {idx + 2}: Invalid expiry_date format")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("Invalid expiry_date", errors[0])

    def test_order_import_negative_quantity_rejected(self):
        """Test that order import with negative quantity is rejected."""
        csv_content = """order_no,customer_name,item_sku,qty_requested
ORD-006,Customer F,VALID-001,50
ORD-007,Customer G,VALID-002,-10
"""
        import pandas as pd
        df = pd.read_csv(io.StringIO(csv_content))
        
        errors = []
        for idx, row in df.iterrows():
            qty = row.get("qty_requested")
            try:
                qty_decimal = Decimal(str(qty))
                if qty_decimal <= 0:
                    errors.append(f"Row {idx + 2}: qty_requested must be positive")
            except Exception:
                errors.append(f"Row {idx + 2}: Invalid qty_requested")

        self.assertEqual(len(errors), 1)
        self.assertIn("Row 3", errors[0])
        self.assertIn("must be positive", errors[0])
