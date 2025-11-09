from django.core.management.base import BaseCommand
from inventory.services.neo4j_sync import sync_graph_to_neo4j


class Command(BaseCommand):
    help = "Sync GraphNode/GraphEdge data to Neo4j (requires settings.NEO4J_ENABLED=True)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-clear",
            action="store_true",
            help="Do not clear the Neo4j database before syncing (default clears).",
        )

    def handle(self, *args, **options):
        clear_first = not options.get("no_clear", False)
        result = sync_graph_to_neo4j(clear_first=clear_first)
        if result is None:
            self.stdout.write(self.style.WARNING("Neo4j sync skipped (disabled or driver missing)."))
        else:
            self.stdout.write(self.style.SUCCESS("Neo4j sync complete."))
