
from django.db.models import Exists, OuterRef
from django.contrib.auth.models import Group
from .models import Unit, TeachingAssistantAssignment

def _in_group_ci(user, names):
    """Case-insensitive group-membership check for any of `names`."""
    try:
        q = None
        for n in names:
            cond = user.groups.filter(name__iexact=n).exists()
            if cond:
                return True
        return False
    except Exception:
        return False

def role_flags(request):
    """Expose booleans for role-based menus.

    Rules:
    - HR: superuser OR in group 'HR'
    - UC: in group 'UC' (or 'Unit Coordinator') OR is lecturer on any Unit
    - TA: in group 'TA' OR has any TeachingAssistantAssignment
    - CASUAL: in group 'CASUAL' OR not HR/UC and not TA
    """
    user = getattr(request, 'user', None)
    data = {'is_hr': False, 'is_uc': False, 'is_ta': False, 'is_casual': False}
    try:
        if not (user and user.is_authenticated):
            return data

        is_hr = bool(getattr(user, 'is_superuser', False)) or _in_group_ci(user, ['HR'])
        # primary detection via group; also fall back to model relation
        is_uc = _in_group_ci(user, ['UC', 'Unit Coordinator']) or Unit.objects.filter(lecturer=user).exists()
        is_ta = _in_group_ci(user, ['TA']) or TeachingAssistantAssignment.objects.filter(user=user).exists()
        # CASUAL if in explicit group, or default fallback when none of the above
        is_casual = _in_group_ci(user, ['CASUAL', 'Casual']) or (not is_hr and not is_uc and not is_ta)

        data.update({'is_hr': is_hr, 'is_uc': is_uc, 'is_ta': is_ta, 'is_casual': is_casual})
        return data
    except Exception:
        return data

def ta_flags(request):
    """Additional TA-related context (units, counts)."""
    user = getattr(request, 'user', None)
    data = {}
    try:
        if user and user.is_authenticated:
            qs = TeachingAssistantAssignment.objects.filter(user=user).select_related('unit')
            data['is_ta'] = qs.exists() or _in_group_ci(user, ['TA'])
            data['ta_assignments'] = qs
            data['ta_units'] = [a.unit for a in qs]
    except Exception:
        pass
    return data
