"""
Management command to load sample data from CSV templates.

Usage:
    python manage.py load_sample_data
    python manage.py load_sample_data --clear  # Clear existing data first
"""
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
import pandas as pd

from inventory.models import Item, Batch, Order, OrderItem


class Command(BaseCommand):
    help = "Load sample data from CSV templates for demo purposes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before loading (WARNING: destructive)',
        )
        parser.add_argument(
            '--path',
            type=str,
            default='sample_data',
            help='Path to sample data directory (default: sample_data)',
        )

    def handle(self, *args, **options):
        clear_data = options.get('clear', False)
        data_path = options.get('path', 'sample_data')
        
        # Resolve path
        if not os.path.isabs(data_path):
            data_path = os.path.join(settings.BASE_DIR, data_path)
        
        if not os.path.exists(data_path):
            self.stdout.write(self.style.ERROR(f"Data path not found: {data_path}"))
            return
        
        items_file = os.path.join(data_path, 'items_template.csv')
        batches_file = os.path.join(data_path, 'batches_template.csv')
        orders_file = os.path.join(data_path, 'orders_template.csv')
        
        # Check files exist
        for f in [items_file, batches_file, orders_file]:
            if not os.path.exists(f):
                self.stdout.write(self.style.ERROR(f"File not found: {f}"))
                return
        
        if clear_data:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            with transaction.atomic():
                OrderItem.objects.all().delete()
                Order.objects.all().delete()
                Batch.objects.all().delete()
                Item.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Existing data cleared."))
        
        # Load items
        self.stdout.write("Loading items...")
        items_df = pd.read_csv(items_file)
        items_created = 0
        
        with transaction.atomic():
            for idx, row in items_df.iterrows():
                try:
                    item, created = Item.objects.update_or_create(
                        sku=str(row['sku']).strip().upper(),
                        defaults={
                            'name': str(row['name']).strip(),
                            'description': str(row.get('description', '')).strip(),
                            'unit': str(row.get('unit', 'pcs')).strip(),
                            'reorder_threshold': Decimal(str(row.get('reorder_threshold', 0))),
                        }
                    )
                    if created:
                        items_created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error loading item row {idx+2}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"Loaded {items_created} items."))
        
        # Load batches
        self.stdout.write("Loading batches...")
        batches_df = pd.read_csv(batches_file)
        batches_created = 0
        
        with transaction.atomic():
            for idx, row in batches_df.iterrows():
                try:
                    item_sku = str(row['item_sku']).strip().upper()
                    item = Item.objects.get(sku=item_sku)
                    
                    received_qty = Decimal(str(row['received_qty']))
                    expiry_date = None
                    if pd.notna(row.get('expiry_date')):
                        expiry_date = pd.to_datetime(row['expiry_date']).date()
                    
                    batch, created = Batch.objects.get_or_create(
                        item=item,
                        lot_no=str(row['lot_no']).strip(),
                        defaults={
                            'received_qty': received_qty,
                            'available_qty': received_qty,
                            'expiry_date': expiry_date,
                            'status': Batch.STATUS_AVAILABLE,
                        }
                    )
                    if created:
                        batches_created += 1
                except Item.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Row {idx+2}: Item '{item_sku}' not found"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error loading batch row {idx+2}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"Loaded {batches_created} batches."))
        
        # Load orders
        self.stdout.write("Loading orders...")
        orders_df = pd.read_csv(orders_file)
        orders_created = 0
        order_items_created = 0
        
        # Group by order_no
        with transaction.atomic():
            for order_no in orders_df['order_no'].unique():
                try:
                    order_rows = orders_df[orders_df['order_no'] == order_no]
                    first_row = order_rows.iloc[0]
                    
                    order, created = Order.objects.get_or_create(
                        order_no=str(first_row['order_no']).strip(),
                        defaults={
                            'customer_name': str(first_row.get('customer_name', '')).strip(),
                            'status': Order.STATUS_NEW,
                        }
                    )
                    if created:
                        orders_created += 1
                    
                    # Create order items
                    for _, row in order_rows.iterrows():
                        try:
                            item_sku = str(row['item_sku']).strip().upper()
                            item = Item.objects.get(sku=item_sku)
                            
                            order_item, oi_created = OrderItem.objects.get_or_create(
                                order=order,
                                item=item,
                                defaults={
                                    'qty_requested': Decimal(str(row['qty_requested'])),
                                }
                            )
                            if oi_created:
                                order_items_created += 1
                        except Item.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f"Item '{item_sku}' not found for order {order_no}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error loading order {order_no}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"Loaded {orders_created} orders with {order_items_created} order items."))
        
        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Sample data loaded successfully!"))
        self.stdout.write(self.style.SUCCESS(f"  Items: {items_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Batches: {batches_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Orders: {orders_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Order Items: {order_items_created}"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
