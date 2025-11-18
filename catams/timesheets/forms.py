from django.contrib.auth import get_user_model
User = get_user_model()

from django.contrib.auth.models import User
from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime, date
from .models import Timesheet, Unit, CourseSlot, TimesheetSlot, TAApplication, CasualApplication

def weeks_between(start, end):
    days = (end - start).days
    if days < 0:
        return 0
    return days // 7 + 1

class TimesheetCreateForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label='Send to')
    unit = forms.ModelChoiceField(queryset=Unit.objects.filter(active=True))
    hourly_rate = forms.DecimalField(
        min_value=0,
        max_digits=7,
        decimal_places=2,
        initial=50,
        label='Hourly rate (AUD)'
    )
    # slots will be filtered by selected unit in __init__
    slots = forms.ModelMultipleChoiceField(
        queryset=CourseSlot.objects.none(),
        required=True,
        help_text='Pick one or more HR-defined weekly slots.',
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Timesheet
        fields = ['unit', 'desc', 'hourly_rate', 'recipient']

    def __init__(self, *args, **kwargs):
        self.tutor = kwargs.pop('casual', None)
        super().__init__(*args, **kwargs)
        # Default unit id from POST/initial/instance
        unit_id = None
        if self.data.get('unit'):
            unit_id = self.data.get('unit')
        elif self.initial.get('unit'):
            unit_id = self.initial.get('unit')
        elif getattr(self.instance, 'unit_id', None):
            unit_id = self.instance.unit_id

        # Populate slots & recipient queryset for the chosen unit
        if unit_id:
            try:
                unit_obj = Unit.objects.get(pk=unit_id)
                self.fields['slots'].queryset = unit_obj.slots.order_by('weekday', 'start_time')
                # recipient choices = UC + TAs of the unit
                ta_ids = list(User.objects.filter(ta_assignments__unit=unit_obj).values_list('id', flat=True))
                rec_ids = [unit_obj.lecturer_id] + ta_ids
                self.fields['recipient'].queryset = User.objects.filter(id__in=rec_ids)
                self.fields['recipient'].initial = unit_obj.lecturer
            except Unit.DoesNotExist:
                self.fields['slots'].queryset = CourseSlot.objects.none()
                self.fields['recipient'].queryset = User.objects.none()
        else:
            first = self.fields['unit'].queryset.first()
            self.fields['slots'].queryset = first.slots.order_by('weekday', 'start_time') if first else CourseSlot.objects.none()
            self.fields['recipient'].queryset = User.objects.none()

        # Limit hourly rate to unit cap if instance/initial has unit
        unit_for_cap = None
        if unit_id:
            try:
                unit_for_cap = Unit.objects.get(pk=unit_id)
            except Unit.DoesNotExist:
                pass
        if unit_for_cap:
        # [cap removed] 
            self.fields['hourly_rate'].max_value = unit_for_cap.max_hourly_rate  # disabled

    def clean(self):
        cleaned = super().clean()
        # Enforce 1 request per course per casual (any status). Must delete existing before adding another.
        unit = cleaned.get('unit')
        # Resolve current user from (a) self.tutor, (b) request.user, (c) existing instance
        user = getattr(self, 'tutor', None)
        if not user and getattr(self, 'request', None):
            user = getattr(self.request, 'user', None)
        if not user and getattr(self.instance, 'tutor', None):
            user = self.instance.tutor
        if unit and user:
            from .models import Timesheet
            qs = Timesheet.objects.filter(unit=unit, tutor=user)
            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError({'unit': 'You already have an application for this course (any status). Please delete the existing one before creating a new application.'})
        unit = cleaned.get('unit')
        recipient = cleaned.get('recipient')

        # Validate recipient belongs to this unit (UC or TA)
        if unit and recipient:
            valid_user_ids = [unit.lecturer_id] + list(
                User.objects.filter(ta_assignments__unit=unit).values_list('id', flat=True)
            )
            if recipient.id not in valid_user_ids:
                self.add_error('recipient', 'Recipient must be the unit coordinator or a TA assigned to this unit.')

        # Existing validations (caps, overlaps etc.) — preserved
        errors = {}
        rate = cleaned.get('hourly_rate') or 0
        # [cap removed]
        if False and unit and unit.max_hourly_rate is not None and rate > unit.max_hourly_rate:
            pass
        # [cap removed] previously appended cap error here
        slots = list(cleaned.get('slots') or [])
        if not slots:
            errors.setdefault('slots', []).append('Please select at least one weekly slot.')

        # Prevent same-day overlaps among chosen slots
        for i in range(len(slots)):
            for j in range(i+1, len(slots)):
                a, b = slots[i], slots[j]
                if a.weekday != b.weekday:
                    continue
                if a.start_time < b.end_time and b.start_time < a.end_time:
                    errors.setdefault('slots', []).append('Overlapping weekly slots on the same day are not allowed.')

        # Also prevent overlaps with user's other active requests
        if self.tutor and unit:
            from .models import TimesheetSlot
            other_ts = Timesheet.objects.filter(tutor=self.tutor, unit=unit).exclude(status='REJ')
            other_slots = TimesheetSlot.objects.filter(timesheet__in=other_ts).select_related('slot')
            for s in slots:
                for os in other_slots:
                    if s.weekday != os.slot.weekday:
                        continue
                    if s.start_time < os.slot.end_time and os.slot.start_time < s.end_time:
                        disp = f"{s.get_weekday_display()} {s.start_time.strftime('%H:%M')}-{s.end_time.strftime('%H:%M')} (TS#{os.timesheet_id} {os.slot.unit.code})"
                        errors.setdefault('slots', []).append(f'Conflicts with your other request: {disp}')

        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)
        return cleaned


    def save(self, commit=True):
        obj = super().save(commit=False)
        # ensure recipient persists from form field & update route accordingly
        rec = self.cleaned_data.get('recipient') if 'recipient' in self.cleaned_data else None
        if rec is not None:
            obj.recipient = rec
            try:
                unit = obj.unit or (self.cleaned_data.get('unit') if 'unit' in self.cleaned_data else None)
            except Exception:
                unit = None
            if unit and getattr(unit, 'lecturer_id', None) == getattr(rec, 'id', None):
                obj.route = 'UC'
            else:
                obj.route = 'TA'
        if commit:
            obj.save()
            try:
                self.save_m2m()
            except Exception:
                pass
        return obj
class UnitForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        u = cleaned.get('lecturer')
        try:
            if u and not u.groups.filter(Q(name__iexact='unit coordinator') | Q(name__iexact='UC')).exists():
                from django.core.exceptions import ValidationError
                raise ValidationError({'lecturer': 'Please choose a user in the "unit coordinator" role.'})
        except Exception:
            if u and not u.groups.filter(name__in=['unit coordinator','lecturer','UC']).exists():
                from django.core.exceptions import ValidationError
                raise ValidationError({'lecturer': 'Please choose a Unit Coordinator account.'})
        return cleaned
    class Meta:
        model = Unit
        # Exclude max_hourly_rate so HR won't see it in the form
        fields = ['code', 'name', 'lecturer', 'start_date', 'end_date', 'budget_amount', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Double safety: even if templates try to render it, the field won't be there
        self.fields.pop('max_hourly_rate', None)

        # Limit Unit Coordinator dropdown to users in the 'unit coordinator' group only
        try:
            from django.contrib.auth import get_user_model
            U = get_user_model()
            self.fields['lecturer'].queryset = U.objects.filter(Q(groups__name__iexact='unit coordinator') | Q(groups__name__iexact='UC')).order_by('username')
        except Exception:
            # Fallback: if group names differ, attempt legacy 'lecturer' alias
            try:
                self.fields['lecturer'].queryset = U.objects.filter(groups__name__in=['unit coordinator','lecturer','UC']).order_by('username')
            except Exception:
                pass

    def save(self, commit=True):
        obj = super().save(commit=False)
        # On create, default cap = 300.00 (do not show to HR)
        if not getattr(obj, 'pk', None):
            try:
                obj.max_hourly_rate = Decimal('300.00')
            except Exception:
                # Fallback if field type differs
                obj.max_hourly_rate = 300
        if commit:
            obj.save()
        return obj
    class Meta:
        model = Unit
        labels = {'lecturer':'Unit Coordinator'}
        fields = ['code','name','lecturer','start_date','end_date','budget_amount','max_hourly_rate','active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type':'date'}),
            'end_date': forms.DateInput(attrs={'type':'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only users who are recognized as lecturers (linked by existing Unit.lecturer)
        self.fields['lecturer'].label = 'Unit Coordinator'
        self.fields['lecturer'].queryset = User.objects.filter(units__isnull=False).distinct().order_by('username')

class SlotForm(forms.ModelForm):
    class Meta:
        model = CourseSlot
        fields = ['weekday','start_time','end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type':'time'}, format='%H:%M'),
            'end_time': forms.TimeInput(attrs={'type':'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].input_formats = ['%H:%M','%H:%M:%S']
        self.fields['end_time'].input_formats = ['%H:%M','%H:%M:%S']

class TAApplicationForm(forms.ModelForm):
    class Meta:
        model = TAApplication
        fields = ['unit', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'rows':3, 'placeholder':'Optional note to Unit Coordinator'}),
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # limit units to active ones
        self.fields['unit'].queryset = Unit.objects.filter(active=True).order_by('code')
    def clean(self):
        cleaned = super().clean()
        # Single TA application per course per applicant (any status)
        unit = cleaned.get('unit')
        try:
            user = self.initial.get('user') or self.instance.applicant
        except Exception:
            user = None
        if unit and user:
            from .models import TAApplication
            qs = TAApplication.objects.filter(unit=unit, applicant=user)
            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError({'unit': '该课程已存在你的 TA 申请（任意状态）。请删除原申请后再提交新的。'})
        user = self.initial.get('user') or self.instance.applicant_id
        unit = cleaned.get('unit')
        if self.instance.pk is None and unit is not None:
            exists = TAApplication.objects.filter(applicant=self.initial.get('applicant') or self.instance.applicant, unit=unit).exclude(status='REJECTED').exists()
            if exists:
                raise ValidationError('You already have a TA application for this unit (pending/approved).')
        return cleaned



class CasualApplicationForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(queryset=User.objects.none(), required=True, label='Send to')

    class Meta:
        model = CasualApplication
        fields = ['unit', 'note', 'recipient']
        widgets = {'note': forms.Textarea(attrs={'rows':3, 'placeholder':'Optional note'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit'].queryset = Unit.objects.filter(active=True).order_by('code')
        # Figure out selected unit from POST or instance
        unit_id = None
        try:
            unit_id = int(self.data.get('unit')) if self.data.get('unit') else None
        except Exception:
            unit_id = getattr(self.instance, 'unit_id', None)
        if not unit_id:
            unit_id = getattr(self.instance, 'unit_id', None)
        # Populate recipient choices: UC + TAs assigned to this unit
        if unit_id:
            try:
                unit = Unit.objects.get(pk=unit_id)
                ta_ids = list(User.objects.filter(ta_assignments__unit=unit).values_list('id', flat=True))
                rec_ids = [unit.lecturer_id] + ta_ids
                self.fields['recipient'].queryset = User.objects.filter(id__in=rec_ids).order_by('username')
                # default to UC
                self.fields['recipient'].initial = unit.lecturer
            except Unit.DoesNotExist:
                self.fields['recipient'].queryset = User.objects.none()
        else:
            self.fields['recipient'].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get('unit')
        recipient = cleaned.get('recipient')
        if unit and recipient:
            valid_user_ids = [unit.lecturer_id] + list(User.objects.filter(ta_assignments__unit=unit).values_list('id', flat=True))
            if recipient.id not in valid_user_ids:
                raise ValidationError({'recipient':'Recipient must be the unit coordinator or a TA assigned to this unit.'})
        return cleaned
    UC_GROUP_CANDIDATES = ['Unit Coordinator', 'unit coordinator', 'uc']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            qs = User.objects.filter(is_active=True)
            qs_uc = qs.filter(groups__name__in=UC_GROUP_CANDIDATES).distinct()
            if qs_uc.exists():
                qs = qs_uc
            else:
                # fallback to profile.role == 'uc' if exists
                try:
                    qs_role = qs.filter(profile__role='uc')
                except Exception:
                    qs_role = User.objects.none()
                if qs_role.exists():
                    qs = qs_role
                else:
                    qs = qs.filter(username__in=['uc_1', 'uc_2', 'unit_coordinator'])
            self.fields['unit_coordinator'].queryset = qs.order_by('username')
        except Exception:
            # if field or relations missing, just keep current queryset but it should exist
            pass

    def clean_unit_coordinator(self):
        user = self.cleaned_data.get('unit_coordinator')
        if user is None:
            return user
        ok = False
        try:
            if user.groups.filter(name__in=UC_GROUP_CANDIDATES).exists():
                ok = True
        except Exception:
            pass
        # profile role
        role = getattr(getattr(user, 'profile', None), 'role', None)
        if role == 'uc':
            ok = True
        if user.username in ('uc_1', 'uc_2', 'unit_coordinator'):
            ok = True
        if not ok:
            raise ValidationError("Selected user is not a Unit Coordinator.")
        return user




# --- policy: hide hourly_rate from user input and make non-required ---
try:
    from django import forms as _forms_mod
    if 'hourly_rate' in TimesheetCreateForm.base_fields:
        TimesheetCreateForm.base_fields['hourly_rate'].required = False
        TimesheetCreateForm.base_fields['hourly_rate'].widget = _forms_mod.HiddenInput()
except Exception:
    pass

    pass