from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User


class Command(BaseCommand):
    help = "Ensure TA group exists and ta_debug belongs only to TA group."

    def handle(self, *args, **options):
        # Ensure TA group
        ta_group_name = "teaching assistant"
        ta_group, _ = Group.objects.get_or_create(name=ta_group_name)

        # Ensure ta_debug exists
        try:
            user = User.objects.get(username="ta_debug")
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING("User 'ta_debug' not found; TA group ensured."))
            return

        # Add into TA
        user.groups.add(ta_group)

        # Remove from CASUAL
        try:
            casual_group = Group.objects.get(name__iexact="CASUAL")
            user.groups.remove(casual_group)
        except Group.DoesNotExist:
            pass

        self.stdout.write(self.style.SUCCESS("Updated 'ta_debug' → TA only"))
