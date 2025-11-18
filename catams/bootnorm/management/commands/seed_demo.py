
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction, connection

class Command(BaseCommand):
    help = "Ensure demo groups, users, a demo unit and a few slots."

    def handle(self, *args, **kwargs):
        ensure_hr_group()
        with transaction.atomic():
            tables = connection.introspection.table_names()
            if "auth_user" not in tables or "auth_group" not in tables:
                self.stdout.write(self.style.ERROR("Required tables not found; run migrate first."))
                return

            # Groups
            hr_g, _ = Group.objects.get_or_create(name="hr")
            lect_g, _ = Group.objects.get_or_create(name="unit coordinator")
            tut_g, _ = Group.objects.get_or_create(name="casual")

            def upsert(username, password, groups, is_staff=False, is_superuser=False):
                u, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
                u.is_active = True
                u.is_staff = is_staff
                u.is_superuser = is_superuser
                u.set_password(password)
                u.save()
                u.groups.set(groups)
                return u

            hr  = upsert("hr_admin", "pass1234", [hr_g], is_staff=True, is_superuser=True)
            lect = upsert("unit_coordinator", "pass1234", [lect_g], is_staff=True, is_superuser=False)
            tut = upsert("casual_user", "pass1234", [tut_g], is_staff=False, is_superuser=False)

            # Old usernames also usable
            upsert("hr", "pass1234", [hr_g], is_staff=True, is_superuser=True)
            upsert("lecturer_a", "pass1234", [lect_g], is_staff=True, is_superuser=False)
            upsert("tutor1", "pass1234", [tut_g], is_staff=False, is_superuser=False)

            # Demo Unit and Slots
            try:
                from timesheets.models import Unit, CourseSlot, TeachingAssistantAssignment
                unit, _ = Unit.objects.get_or_create(code="DEMO101", defaults={"name":"Demo Unit", "lecturer": lect, "active": True})
                # Create a couple of weekly slots, if none exist
                if not Slot.objects.filter(unit=unit).exists():
                    # Weekday choices in model are likely 0-6; we'll use 1 (Mon) and 3 (Wed)
                    from datetime import time
                    CourseSlot.objects.create(unit=unit, weekday=0, start_time=time(9,0), end_time=time(11,0))
                    CourseSlot.objects.create(unit=unit, weekday=2, start_time=time(14,0), end_time=time(16,0))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Could not create demo unit/slots: {e!r}"))

            self.stdout.write(self.style.SUCCESS("Demo users/groups/unit/slots ensured."))


def ensure_hr_group():
    hr_group, _ = Group.objects.get_or_create(name='HR')
    try:
        u = User.objects.get(username='hr_admin')
        u.groups.add(hr_group)
        u.save()
    except User.DoesNotExist:
        pass


def ensure_extra_users(unit):
    from django.contrib.auth.models import User
    def get_or_create_user(username, password, first, last):
        u, _ = User.objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last})
        u.set_password(password); u.save(); return u
    c1 = get_or_create_user('casual_user1', 'pass1234', 'Casual', 'One')
    c2 = get_or_create_user('casual_user2', 'pass1234', 'Casual', 'Two')
    ta = get_or_create_user('ta_user', 'pass1234', 'TA', 'User')
    # No default TA assignment; TA must be approved first.

