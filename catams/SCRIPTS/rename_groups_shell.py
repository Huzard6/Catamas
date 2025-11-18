# One-off script to be piped into: python manage.py shell < SCRIPTS/rename_groups_shell.py
from django.contrib.auth.models import Group, Permission
from django.apps import apps
from django.db import transaction

TARGETS = ["casual", "unit coordinator", "hr"]
ALIASES = {
    "tutor": "casual",
    "Tutor": "casual",
    "Tutors": "casual",
    "lecturer": "unit coordinator",
    "Lecturer": "unit coordinator",
    "Lecturers": "unit coordinator",
    "hr": "hr",
    "HR": "hr",
}

def ensure_target_groups():
    for name in TARGETS:
        Group.objects.get_or_create(name=name)

@transaction.atomic
def merge_groups():
    ensure_target_groups()
    for old, new in ALIASES.items():
        try:
            old_g = Group.objects.get(name=old)
        except Group.DoesNotExist:
            continue
        new_g = Group.objects.get(name=new)
        # Move permissions
        new_g.permissions.add(*old_g.permissions.all())
        # Move users
        for u in old_g.user_set.all():
            u.groups.add(new_g)
            u.groups.remove(old_g)
        if old_g != new_g:
            old_g.delete()
            print(f"Merged group '{old}' -> '{new}'")

def try_update_role_fields():
    # Try to update any model instances having a 'role' field with string values
    mapping = {"tutor": "casual", "Tutor": "casual", "lecturer": "unit coordinator", "Lecturer": "unit coordinator"}
    updated_total = 0
    for model in apps.get_models():
        fields = [f.name for f in model._meta.get_fields() if hasattr(f, 'attname')]
        if "role" in fields:
            try:
                qs = model.objects.filter(role__in=list(mapping.keys()))
                cnt = qs.count()
                if cnt:
                    for old, new in mapping.items():
                        qs.filter(role=old).update(role=new)
                    updated_total += cnt
                    print(f"Updated {cnt} rows in {model.__name__}.role")
            except Exception as e:
                # model may be unmanaged or not suitable for updates; skip
                pass
    print(f"Done updating role fields. Total rows touched: {updated_total}")

if __name__ == "__main__":
    merge_groups()
    try_update_role_fields()
    print("Completed roles normalization to: casual, unit coordinator, hr.")
