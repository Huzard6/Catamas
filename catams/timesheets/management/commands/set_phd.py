from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from timesheets.models import UserProfile

class Command(BaseCommand):
    help = "Set a user's PhD flag. Usage: manage.py set_phd --user <username> --phd 1|0"

    def add_arguments(self, parser):
        parser.add_argument('--user', required=True, help='Username')
        parser.add_argument('--phd', required=True, type=int, choices=[0,1], help='1 for PhD, 0 for non-PhD')

    def handle(self, *args, **opts):
        uname = opts['user']
        flag = bool(opts['phd'])
        try:
            u = User.objects.get(username=uname)
        except User.DoesNotExist:
            raise CommandError(f'User not found: {uname}')
        prof, _ = UserProfile.objects.get_or_create(user=u)
        prof.is_phd = flag
        prof.save()
        self.stdout.write(self.style.SUCCESS(f'Set {uname}.profile.is_phd = {flag}'))
