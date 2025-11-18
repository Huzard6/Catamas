from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from timesheets.models import Unit, CourseSlot
from datetime import date, time, timedelta

class Command(BaseCommand):
    help = "Ensure demo users/units/slots WITHOUT deleting data (UC primary is uc_1)."

    def handle(self, *args, **kwargs):
        def ensure(username, staff=False, superuser=False):
            u, _ = User.objects.get_or_create(username=username)
            u.is_staff = staff or superuser
            u.is_superuser = superuser
            u.set_password('pass1234')
            u.save()
            return u

        # Base users
        hr  = ensure('hr',  superuser=True)
        uc1 = ensure('uc_1', staff=True)
        ensure('tutor1')  # legacy demo user still available

        # Demo units owned by uc_1
        start = date.today()
        end = start + timedelta(days=30)

        u1, _ = Unit.objects.get_or_create(
            code='COMP5310',
            defaults=dict(name='Machine Learning', lecturer=uc1, max_hourly_rate=60,
                          start_date=start, end_date=end, budget_amount=10000)
        )
        if u1.lecturer != uc1:
            u1.lecturer = uc1
            u1.save()

        u2, _ = Unit.objects.get_or_create(
            code='COMP5020',
            defaults=dict(name='Databases', lecturer=uc1, max_hourly_rate=55,
                          start_date=start, end_date=end, budget_amount=8000)
        )
        if u2.lecturer != uc1:
            u2.lecturer = uc1
            u2.save()

        # Ensure canonical slots (create if missing)
        for unit, weekday, st, et in [
            (u1, 1, time(16,0), time(17,0)),
            (u1, 1, time(18,0), time(19,0)),
            (u2, 3, time(9,0),  time(11,0)),
        ]:
            CourseSlot.objects.get_or_create(unit=unit, weekday=weekday, start_time=st, end_time=et)

        self.stdout.write(self.style.SUCCESS('Demo ensured (no deletions); UC is uc_1 for COMP5310/COMP5020.'))