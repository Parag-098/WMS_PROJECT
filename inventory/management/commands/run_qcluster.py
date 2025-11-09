"""
Management command to run Django-Q cluster.
Wrapper for convenience; alternatively use: python manage.py qcluster
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run Django-Q cluster for background task processing."

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            type=int,
            default=4,
            help='Number of worker processes (default: 4)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Django-Q cluster..."))
        call_command('qcluster')
