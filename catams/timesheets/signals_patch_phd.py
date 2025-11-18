from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import User
from timesheets.models import UserProfile

TARGETS = {'casual_2','casual_debug2'}

@receiver(user_logged_in)
def ensure_demo_users_phd(sender, user, request, **kwargs):
    try:
        if user.username in TARGETS:
            prof, _ = UserProfile.objects.get_or_create(user=user)
            if not prof.is_phd:
                prof.is_phd = True
                prof.save(update_fields=['is_phd'])
    except Exception:
        # avoid blocking login
        pass
