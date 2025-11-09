"""
Management command to manually trigger expiry scan.

Usage:
    python manage.py run_expiry_scan
    python manage.py run_expiry_scan --dry-run  # Preview only, no changes
"""
from django.core.management.base import BaseCommand
from inventory.tasks import scheduled_expiry_scan


class Command(BaseCommand):
    help = "Manually trigger the expiry scan task to check for expired and near-expiry batches."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview results without making changes or creating notifications',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE: No changes will be made."))
            self.stdout.write("")
            
            # Import necessary models for dry run
            from datetime import timedelta
            from django.utils import timezone
            from inventory.models import Batch
            
            today = timezone.now().date()
            warning_threshold = today + timedelta(days=7)
            
            # Find expired batches
            expired = Batch.objects.filter(
                expiry_date__lt=today,
                status=Batch.STATUS_AVAILABLE,
                available_qty__gt=0
            ).select_related('item')
            
            # Find near-expiry batches
            near_expiry = Batch.objects.filter(
                expiry_date__gte=today,
                expiry_date__lte=warning_threshold,
                status=Batch.STATUS_AVAILABLE,
                available_qty__gt=0
            ).select_related('item')
            
            # Display results
            if expired.exists():
                self.stdout.write(self.style.ERROR(f"Found {expired.count()} expired batch(es):"))
                for batch in expired:
                    self.stdout.write(f"  - {batch.item.sku} | Lot: {batch.lot_no} | Expired: {batch.expiry_date} | Qty: {batch.available_qty}")
                self.stdout.write("")
            else:
                self.stdout.write(self.style.SUCCESS("No expired batches found."))
                self.stdout.write("")
            
            if near_expiry.exists():
                self.stdout.write(self.style.WARNING(f"Found {near_expiry.count()} near-expiry batch(es):"))
                for batch in near_expiry:
                    self.stdout.write(f"  - {batch.item.sku} | Lot: {batch.lot_no} | Expires: {batch.expiry_date} | Qty: {batch.available_qty}")
                self.stdout.write("")
            else:
                self.stdout.write(self.style.SUCCESS("No near-expiry batches found."))
                self.stdout.write("")
            
            self.stdout.write(self.style.SUCCESS("Dry run complete. Use without --dry-run to apply changes."))
            
        else:
            # Run actual expiry scan
            self.stdout.write("Running expiry scan...")
            
            try:
                result = scheduled_expiry_scan()
                
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("Expiry scan completed successfully!"))
                self.stdout.write(f"  Expired batches marked: {result['expired_count']}")
                self.stdout.write(f"  Near-expiry batches found: {result['near_expiry_count']}")
                self.stdout.write("")
                
                if result['expired_count'] > 0:
                    self.stdout.write(self.style.WARNING(
                        f"→ {result['expired_count']} batch(es) have been marked as EXPIRED."
                    ))
                
                if result['near_expiry_count'] > 0:
                    self.stdout.write(self.style.WARNING(
                        f"→ {result['near_expiry_count']} batch(es) will expire within 7 days."
                    ))
                
                self.stdout.write("")
                self.stdout.write("Notifications have been created for warehouse managers.")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error running expiry scan: {e}"))
                raise
