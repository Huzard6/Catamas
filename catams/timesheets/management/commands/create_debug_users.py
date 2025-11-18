from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from timesheets.models import Unit, CourseSlot, TeachingAssistantAssignment
from datetime import date, time, timedelta

class Command(BaseCommand):
    help = "Normalize demo users: remove hr_debug; keep hr; set UCs to uc_1/uc_2; keep TA & casuals; ensure DEBUG100 -> uc_2."

    def handle(self, *args, **kwargs):
        def ensure_user(username, password="pass1234", is_staff=False, is_superuser=False):
            u, _ = User.objects.get_or_create(username=username)
            u.is_staff = is_staff or is_superuser
            u.is_superuser = is_superuser
            u.set_password(password)
            u.save()
            return u

        def ensure_or_rename(old_name, new_name, *, is_staff=False, is_superuser=False):
            # If new_name already exists, normalize flags/password and return
            try:
                u = User.objects.get(username=new_name)
            except User.DoesNotExist:
                # If old_name exists, rename it; otherwise create new
                try:
                    u = User.objects.get(username=old_name)
                    u.username = new_name
                except User.DoesNotExist:
                    u = User(username=new_name)
            u.is_staff = is_staff or is_superuser
            u.is_superuser = is_superuser
            u.set_password('pass1234')
            u.save()
            return u

        # Remove old HR debug if present
        User.objects.filter(username="hr_debug").delete()

        # HR superuser
        hr = ensure_or_rename("hr", "hr", is_staff=True, is_superuser=True)

        # UCs: lecturer_a -> uc_1, uc_debug -> uc_2
        uc1 = ensure_or_rename("lecturer_a", "uc_1", is_staff=True, is_superuser=False)
        uc2 = ensure_or_rename("uc_debug", "uc_2", is_staff=True, is_superuser=False)

        # TA & casuals (unchanged names)
        ta_debug = ensure_or_rename("ta_debug", "ta_debug", is_staff=False)
        casual1  = ensure_or_rename("casual_debug1", "casual_debug1", is_staff=False)
        casual2  = ensure_or_rename("casual_debug2", "casual_debug2", is_staff=False)

        # HR group for compatibility (not necessary for 'hr' superuser)
        Group.objects.get_or_create(name="hr")

        # Ensure a DEBUG unit owned by uc_2
        start = date.today()
        end = start + timedelta(days=30)
        unit, _ = Unit.objects.get_or_create(
            code="DEBUG100",
            defaults=dict(
                name="Debugging 101",
                lecturer=uc2,
                max_hourly_rate=50,
                start_date=start,
                end_date=end,
                budget_amount=5000,
            )
        )
        if unit.lecturer != uc2:
            unit.lecturer = uc2
            unit.save()

        # Ensure a couple of slots
        for spec in [
            dict(weekday=1, start_time=time(10,0), end_time=time(11,0)),
            dict(weekday=3, start_time=time(14,0), end_time=time(15,0)),
        ]:
            CourseSlot.objects.get_or_create(unit=unit, **spec)

        # Ensure TA assignment (opt-in via env); default is **no auto-assignment**
        import os as _os
        if _os.getenv("CATAMS_DEMO_ASSIGN_TA", "0") == "1":
            TeachingAssistantAssignment.objects.get_or_create(user=ta_debug, unit=unit)
        else:
            # If previously auto-assigned, remove it to reflect 'not a TA until approved' policy
            TeachingAssistantAssignment.objects.filter(user=ta_debug, unit=unit).delete()

        self.stdout.write(self.style.SUCCESS(
            "Users set: hr; uc_1/uc_2; ta_debug; casual_debug1/2. Removed hr_debug. DEBUG100 -> uc_2."
        ))

        # ## AUTO-PHD-PATCH: ensure casual_2/casual_debug2 are marked as PhD
        try:
            from timesheets.models import UserProfile
            for uname in ["casual_2", "casual_debug2"]:
                try:
                    u = User.objects.get(username=uname)
                    prof, _ = UserProfile.objects.get_or_create(user=u)
                    prof.is_phd = True
                    prof.save()
                except User.DoesNotExist:
                    pass
        except Exception:
            pass
        # ## END AUTO-PHD-PATCH
        
