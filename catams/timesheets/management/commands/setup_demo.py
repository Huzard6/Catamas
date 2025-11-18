
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from timesheets.models import Unit, CourseSlot
from datetime import date, time, timedelta

class Command(BaseCommand):
    help = 'Create demo users and sample courses/slots'

    def handle(self, *args, **kwargs):
        def ensure(username, staff=False, superuser=False):
            u, _ = User.objects.get_or_create(username=username)
            u.is_staff = staff or superuser
            u.is_superuser = superuser
            u.set_password('pass1234')
            u.save()
            return u

        hr = ensure('hr', superuser=True)
        lect = ensure('lecturer_a', staff=False)
        tut = ensure('tutor1')

        # Reset demo data
        CourseSlot.objects.all().delete()
        Unit.objects.all().delete()

        start = date.today()
        end = start + timedelta(days=30)

        u1 = Unit.objects.create(code='COMP5310', name='Machine Learning', lecturer=lect, max_hourly_rate=60,
                                 start_date=start, end_date=end, budget_amount=10000)
        u2 = Unit.objects.create(code='COMP5020', name='Databases', lecturer=lect, max_hourly_rate=55,
                                 start_date=start, end_date=end, budget_amount=8000)

        CourseSlot.objects.bulk_create([
            CourseSlot(unit=u1, weekday=1, start_time=time(16,0), end_time=time(17,0)), # Tue 4-5
            CourseSlot(unit=u1, weekday=1, start_time=time(18,0), end_time=time(19,0)), # Tue 6-7
            CourseSlot(unit=u2, weekday=3, start_time=time(9,0),  end_time=time(11,0)), # Thu 9-11
        ])

        self.stdout.write(self.style.SUCCESS('Users: hr / lecturer_a / tutor1 (pass1234). Demo units & slots created.'))
