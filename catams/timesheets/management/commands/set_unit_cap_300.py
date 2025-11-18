from django.core.management.base import BaseCommand
from decimal import Decimal
from timesheets.models import Unit

class Command(BaseCommand):
    help = "Set max_hourly_rate = 300.00 for all Unit rows."

    def handle(self, *args, **options):
        updated = 0
        for u in Unit.objects.all():
            try:
                u.max_hourly_rate = Decimal('300.00')
            except Exception:
                u.max_hourly_rate = 300
            u.save(update_fields=['max_hourly_rate'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} Unit rows to max_hourly_rate=300.00"))
