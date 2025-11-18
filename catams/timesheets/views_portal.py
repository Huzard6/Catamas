from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.apps import apps
from django.db.models import Q
from django import forms
from timesheets.models import Timesheet, CourseSlot

from datetime import datetime, date
from decimal import Decimal
def _get_high_low_rates(ts):
    phd = False
    try:
        phd = bool(getattr(getattr(ts.tutor, 'profile', None), 'is_phd', False))
    except Exception:
        phd = False
    high = Decimal('193.68') if phd else Decimal('162.12')
    low  = Decimal('129.13') if phd else Decimal('108.08')
    return high, low


def _policy_compute(ts):
    """Return dict with policy-based rates and totals for a timesheet."""
    phd = bool(getattr(getattr(ts.tutor, 'profile', None), 'is_phd', False))
    HIGH = Decimal('193.68') if phd else Decimal('162.12')
    LOW  = Decimal('129.13') if phd else Decimal('108.08')
    # Collect selected slots durations per week (hours) and order by weekday+start
    slots = [t.slot for t in ts.selected_slots.select_related('slot').all()]
    durs = []
    for s in slots:
        try:
            dt0 = datetime.combine(date.min, s.start_time)
            dt1 = datetime.combine(date.min, s.end_time)
            secs = (dt1 - dt0).total_seconds()
            hrs = Decimal(str(secs)) / Decimal('3600') if secs > 0 else Decimal('0')
        except Exception:
            hrs = Decimal('0')
        durs.append((getattr(s, 'weekday', 0), getattr(s, 'start_time', None), hrs))
    durs.sort(key=lambda x: (x[0], x[1] or ''))
    hours_week = sum((x[2] for x in durs), Decimal('0'))
    first_hours = durs[0][2] if durs else Decimal('0')
    try:
        weeks = weeks_between(ts.unit.start_date, ts.unit.end_date)
    except Exception:
        # simple fallback: 5 weeks if utils unavailable
        try:
            delta_days = (ts.unit.end_date - ts.unit.start_date).days
            weeks = max(1, int(delta_days//7)+1)
        except Exception:
            weeks = 1
    total = (first_hours*HIGH + (hours_week-first_hours)*LOW) * Decimal(str(weeks))
    total = total.quantize(Decimal('0.01'))
    return {
        'policy_high': HIGH,
        'policy_low': LOW,
        'policy_hours_per_week': hours_week.quantize(Decimal('0.01')),
        'policy_weeks': weeks,
        'policy_total_hours': (hours_week*Decimal(str(weeks))).quantize(Decimal('0.01')),
        'policy_total': total,
    }
def _feature_casual_apps_enabled():
    return getattr(settings, 'FEATURE_CASUAL_APPLICATIONS', False)
from django.contrib.auth.decorators import login_required, user_passes_test

# Fallback group_required decorator if not present
def group_required(name):
    def _dec(view_func):
        return user_passes_test(lambda u: u.is_authenticated and u.groups.filter(name__iexact=name).exists())(view_func)
    return _dec
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Subquery
from django.contrib.auth import get_user_model
User = get_user_model()
from .models import CasualChangeRequest, Unit, CourseSlot, TeachingAssistantAssignment
from django.contrib import messages
from django.http import JsonResponse
from django.forms import inlineformset_factory
from .models import Unit, CourseSlot, Timesheet, TimesheetSlot, TAApplication, TeachingAssistantAssignment, CasualApplication
from .forms import TimesheetCreateForm, UnitForm, SlotForm, weeks_between, weeks_between, TAApplicationForm, CasualApplicationForm


from decimal import Decimal
from datetime import datetime, date


from django.db import transaction

def _force_delete_unit(unit):
    """Delete all related records to a Unit in a safe order, then delete the Unit."""
    with transaction.atomic():
        TimesheetSlot.objects.filter(timesheet__unit=unit).delete()
        Timesheet.objects.filter(unit=unit).delete()
        TAApplication.objects.filter(unit=unit).delete()
        CasualApplication.objects.filter(unit=unit).delete()
        TeachingAssistantAssignment.objects.filter(unit=unit).delete()
        CourseSlot.objects.filter(unit=unit).delete()
        unit.delete()

def _calc_total_pay(unit, hourly_rate, slots):
    # rate cap
    rate = Decimal(str(hourly_rate))
    try:
        cap = Decimal(str(unit.max_hourly_rate))
        # [cap removed]
        if False and rate > cap: rate = cap
    except Exception:
        pass
    # weekly hours
    weekly_hours = Decimal('0')
    for s in slots:
        dt0 = datetime.combine(date.min, s.start_time)
        dt1 = datetime.combine(date.min, s.end_time)
        secs = (dt1 - dt0).total_seconds()
        if secs > 0:
            weekly_hours += Decimal(str(secs)) / Decimal('3600')
    weeks = weeks_between(unit.start_date, unit.end_date)
    total = (weekly_hours * Decimal(str(weeks)) * rate).quantize(Decimal('0.01'))
    return total


def role(user):
    """Resolve a user's primary role.
    HR > UC(lecturer) > TA > CASUAL.
    Groups are matched case-insensitively.
    """
    try:
        # HR first
        if getattr(user, 'is_superuser', False) or user.groups.filter(name__iexact='HR').exists():
            return 'HR'
    except Exception:
        pass
    try:
        # UC by group or by being listed as Unit.lecturer
        if user.groups.filter(name__iexact='UC').exists():
            return 'LECT'
    except Exception:
        pass
    try:
        from .models import Unit, TeachingAssistantAssignment as TAA
        if Unit.objects.filter(lecturer=user).exists():
            return 'LECT'
        # TA via group or assignment
        if user.groups.filter(name__iexact='TA').exists() or user.groups.filter(name__iexact='teaching assistant').exists() or TAA.objects.filter(user=user).exists():
            return 'TA'
    except Exception:
        # If models are unavailable on import-time, ignore
        pass
    try:
        # Explicit casual group
        if user.groups.filter(name__iexact='CASUAL').exists():
            return 'casual'
    except Exception:
        pass
    # Fallback: casual
    return 'casual'

def base_ctx(request):
    r = role(request.user)
    return {
        'is_hr': r=='HR',
        'is_lecturer': r=='LECT',
        'is_tutor': r=='casual',
        'is_ta': r=='TA',
    }

@login_required
def home(request):
    r = role(request.user)
    if r=='HR':
        return redirect('hr-courses')
    if r=='LECT':
        # lecturer dashboard: per course → per slot → tutors (FINAL only)
        units = Unit.objects.filter(lecturer=request.user).prefetch_related('slots')
        rows = []
        for u in units:
            slot_rows = []
            for s in u.slots.all().order_by('weekday','start_time'):
                tutors = list(
                    TimesheetSlot.objects.filter(slot=s, timesheet__unit=u, timesheet__status='FINAL')
                    .values_list('timesheet__tutor__username', flat=True).distinct()
                )
                slot_rows.append({'slot': s, 'tutors': tutors})
            rows.append({'unit': u, 'slots': slot_rows})
        return render(request, 'timesheets/dashboard_lecturer.html', {**base_ctx(request), 'rows': rows})
    return redirect('casual-requests')

# tutor
@login_required
def tutor_requests(request):
    if role(request.user) == 'TA':
        return redirect('ta_request')
    items = Timesheet.objects.filter(tutor=request.user).order_by('-created_at')
    return render(request, 'timesheets/tutor_requests.html', {**base_ctx(request), 'items': items})


@login_required
def tutor_new(request):
    """Full 'New Request' page (unit, desc, slots, hourly_rate...).
    Keeps one-per-course rule and normal save flow.
    """
    form = TimesheetCreateForm(request.POST or None, tutor=request.user)
    if request.method == 'POST' and form.is_valid():
        # Second-line guard: prevent multiple requests for the same course by this user
        unit = form.cleaned_data.get('unit')
        exists = Timesheet.objects.filter(unit=unit, tutor=request.user)
        if form.instance and getattr(form.instance, 'pk', None):
            exists = exists.exclude(pk=form.instance.pk)
        if unit and exists.exists():
            form.add_error('unit', 'You already have an application for this course (any status). Please delete the existing one before creating a new application.')
            units = Unit.objects.filter(active=True).prefetch_related('slots')
            return render(request, 'timesheets/tutor_new.html', {**base_ctx(request), 'form': form, 'units': units})
        # Save draft
        ts = form.save(commit=False)
        ts.tutor = request.user
        # recipient & route
        rec = form.cleaned_data.get('recipient')
        ts.recipient = rec
        ts.route = 'TA' if (rec and rec.id != ts.unit.lecturer_id) else 'UC'
        ts.save()
        # Save selected slots
        selected = list(form.cleaned_data.get('slots', []))
        TimesheetSlot.objects.bulk_create([TimesheetSlot(timesheet=ts, slot=s) for s in selected])
        # Calculate total pay
        try:
            ts.total_pay = _calc_total_pay(ts.unit, ts.hourly_rate, selected)
            ts.save()
        except Exception:
            pass
        messages.success(request, 'Saved as draft. Click Send when ready.')
        return redirect('casual-requests')
    units = Unit.objects.filter(active=True).prefetch_related('slots')
    return render(request, 'timesheets/tutor_new.html', {**base_ctx(request), 'form': form, 'units': units})

@login_required

def hr_course_delete(request, pk):
    if role(request.user) != 'HR':
        messages.error(request, 'Permission denied.')
        return redirect('portal-home')
    unit = get_object_or_404(Unit, pk=pk)
    try:
        _force_delete_unit(unit)
        messages.success(request, 'Course and ALL related records were deleted.')
    except Exception as e:
        messages.error(request, f'Force delete failed: {e}')
    return redirect('hr-courses')


@login_required
def unit_api(request, unit_id:int):
    unit = get_object_or_404(Unit, pk=unit_id, active=True)

    # recipients: UC + APPROVED TA applicants for this unit
    recipients = []
    uc = unit.lecturer
    uc_label = f"Unit Coordinator — {uc.get_full_name() or uc.username}"
    recipients.append({'id': uc.id, 'label': uc_label})
    for app in TAApplication.objects.filter(unit=unit, status='APPROVED').select_related('applicant'):
        u = app.applicant
        recipients.append({'id': u.id, 'label': f"Teaching Assistant — {u.get_full_name() or u.username}"})

    # recipients: UC + TAs APPROVED for this unit
    recipients = []
    uc = unit.lecturer
    uc_label = f"Unit Coordinator — {uc.get_full_name() or uc.username}"
    recipients.append({'id': uc.id, 'label': uc_label})
    for app in TAApplication.objects.filter(unit=unit, status='APPROVED').select_related('applicant'):
        u = app.applicant
        recipients.append({'id': u.id, 'label': f"Teaching Assistant — {u.get_full_name() or u.username}"})
        # Build human-readable labels for slots
    def fmt(t): return t.strftime('%H:%M')
    slots = []
    for s in unit.slots.all().order_by('weekday','start_time'):
        label = f"{s.get_weekday_display()} {fmt(s.start_time)}–{fmt(s.end_time)}"
        # compute duration in hours
        d = (datetime.combine(date.today(), s.end_time) - datetime.combine(date.today(), s.start_time)).total_seconds()/3600.0
        slots.append({'id': s.id, 'label': label, 'duration_hours': d})
    return JsonResponse({ 'recipients': recipients, 'uc_id': uc.id, 
        'start_date': unit.start_date.isoformat(),
        'end_date': unit.end_date.isoformat(),
        'max_hourly_rate': float(unit.max_hourly_rate),
        'slots': slots,
    })

@login_required
def lecturer_courses(request):
    if role(request.user)!='LECT': return redirect('portal-home')
    units = Unit.objects.filter(lecturer=request.user).prefetch_related('slots')
    return render(request, 'timesheets/lecturer_courses.html', {**base_ctx(request), 'units':units})

@login_required
def tutor_resubmit(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, tutor=request.user)
    if ts.status not in ('FINAL','REJ'):
        messages.error(request, 'Only FINAL or REJECTED requests can be resubmitted.')
        return redirect('casual-requests')
    # block resubmit if another request for same unit exists (non-REJ)
    conflict = Timesheet.objects.filter(tutor=request.user, unit=ts.unit).exclude(status='REJ').exclude(pk=ts.pk).first()
    if conflict:
        messages.error(request, f'You already have request #{conflict.pk} for this unit (status {conflict.status}). Please delete it or continue with that one.')
        return redirect('casual-requests')
    if request.method == 'POST':
        # Overwrite-style resubmit: move back to DRAFT
        ts.status = 'DRAFT'
        ts.save()
        messages.success(request, 'This request has been moved back to DRAFT. You can edit and send it again.')
        return redirect('casual-requests')
    # GET: show confirmation page
    return render(request, 'timesheets/tutor_resubmit_confirm.html', {**base_ctx(request), 'ts': ts})

@login_required
def tutor_delete(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, tutor=request.user)
    if ts.status not in ('REJ','DRAFT'):
        messages.error(request, 'Only DRAFT or REJECTED requests can be deleted.')
        return redirect('casual-requests')
    if request.method == 'POST':
        ts.delete()
        messages.success(request, 'Deleted.')
        return redirect('casual-requests')
    return render(request, 'timesheets/tutor_delete_confirm.html', {**base_ctx(request), 'ts': ts})




@login_required
def tutor_detail(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, tutor=request.user)
    ctx = {**base_ctx(request), 'ts': ts}
    # Compute base policy values
    base_total = Decimal('0')
    base_hours = Decimal('0')
    high = low = None
    try:
        _d = _policy_compute(ts)
        high = _d.get('policy_high'); low = _d.get('policy_low')
        base_total = Decimal(str(_d.get('policy_total') or 0))
        base_hours = Decimal(str(_d.get('hours') or 0))
        ctx.update(_d)
    except Exception:
        pass
    # UC manual deltas
    m_hours = Decimal(str(getattr(ts, 'manual_hours_delta', 0) or 0))
    m_pay = Decimal(str(getattr(ts, 'manual_pay_delta', 0) or 0))
    # Effective totals
    eff_total = (base_total + m_pay).quantize(Decimal('0.01'))
    eff_hours_val = (base_hours + m_hours)
    eff_hours = eff_hours_val.quantize(Decimal('0.01')) if eff_hours_val != 0 else Decimal('0.00')
    # Display
    if high is not None and low is not None:
        ts.hourly_rate = f"{high:.2f} / {low:.2f}"
    ts.total_pay = f"{eff_total:.2f}"
    return render(request, 'timesheets/tutor_detail.html', ctx)
    return render(request, 'timesheets/tutor_detail.html', ctx)

@login_required
def tutor_edit(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, tutor=request.user)
    if ts.status not in ('DRAFT','REJ'):
        messages.error(request, 'Current status does not allow editing.')
        return redirect('casual-requests')
    initial = {'slots': [s.slot_id for s in ts.selected_slots.all()]}
    form = TimesheetCreateForm(request.POST or None, instance=ts, tutor=request.user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not getattr(obj, 'new_rate', None):
            obj.new_rate = Decimal('50.00')

        from decimal import Decimal as _D

        if getattr(obj, 'hourly_rate', None) in (None, ''):

            obj.hourly_rate = _D('0.00')

        obj.total_pay = getattr(form, '_calculated_total', 0)
        obj.save()
        TimesheetSlot.objects.filter(timesheet=obj).delete()
        selected = list(form.cleaned_data.get('slots', []))
        TimesheetSlot.objects.bulk_create([TimesheetSlot(timesheet=obj, slot=s) for s in selected])
        obj.total_pay = _calc_total_pay(obj.unit, obj.hourly_rate, selected)
        obj.save(update_fields=['total_pay'])
        messages.success(request, 'Saved.')
        return redirect('casual-detail', pk=obj.pk)
    return render(request, 'timesheets/tutor_edit.html', {**base_ctx(request), 'form': form, 'ts': ts})

# ===== Teaching Assistant Application Views =====
@login_required

def ta_new(request):
    if request.user.is_staff or request.user.is_superuser:
        messages.error(request, "HR cannot create TA applications.")
        return redirect('/portal/')
    if request.method == 'POST':
        form = TAApplicationForm(request.POST, instance=TAApplication(applicant=request.user))
        if form.is_valid():
            app = form.save(commit=False)
            app.applicant = request.user
            # prevent duplicate active apps
            if TAApplication.objects.filter(applicant=request.user, unit=app.unit).exclude(status='REJECTED').exists():
                messages.error(request, 'You already have a TA application for this unit (pending/approved).')
                return redirect('/portal/ta/my/')
            app.status = 'TO_UC'
            app.save()
            messages.success(request, "TA application submitted to the Unit Coordinator.")
            return redirect('/portal/ta/my/')
    else:
        form = TAApplicationForm(instance=TAApplication(applicant=request.user))
    return render(request, 'timesheets/ta_new.html', {'form': form})

@login_required
def ta_my(request):
    qs = TAApplication.objects.filter(applicant=request.user).order_by('-created_at')
    return render(request, 'timesheets/ta_my.html', {'apps': qs})

@login_required
def uc_ta_inbox(request):
    # UC sees applications for units where he/she is lecturer
    units = Unit.objects.filter(lecturer=request.user)
    qs = TAApplication.objects.filter(unit__in=units, status='TO_UC').order_by('created_at')
    return render(request, 'timesheets/uc_ta_inbox.html', {'apps': qs})

@login_required
def uc_ta_forward(request, pk):
    app = get_object_or_404(TAApplication, pk=pk, status='TO_UC')
    if app.unit.lecturer != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Not authorized to forward this application.")
        return redirect('/portal/unit-coordinator/ta-requests/')
    if request.method == 'POST':
        note = request.POST.get('uc_note','').strip()
        app.uc_note = note
        app.status = 'TO_HR'
        app.save()
        messages.success(request, "Application forwarded to HR.")
    return redirect('/portal/unit-coordinator/ta-requests/')

@login_required
def uc_ta_reject(request, pk):
    app = get_object_or_404(TAApplication, pk=pk, status='TO_UC')
    if app.unit.lecturer != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Not authorized to reject this application.")
        return redirect('/portal/unit-coordinator/ta-requests/')
    if request.method == 'POST':
        note = request.POST.get('uc_note','').strip()
        app.uc_note = note
        app.status = 'REJECTED'
        app.save()
        messages.success(request, "Application rejected.")
    return redirect('/portal/unit-coordinator/ta-requests/')

@login_required
def hr_ta_inbox(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    qs = TAApplication.objects.filter(status='TO_HR').order_by('created_at')
    return render(request, 'timesheets/hr_ta_inbox.html', {'apps': qs})

@login_required
def hr_ta_approve(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    app = get_object_or_404(TAApplication, pk=pk, status='TO_HR')
    if request.method == 'POST':
        note = request.POST.get('hr_note', '').strip()
        app.hr_note = note
        app.status = 'APPROVED'
        app.save()
        TeachingAssistantAssignment.objects.get_or_create(user=app.applicant, unit=app.unit)
        messages.success(request, "Application approved.")
    return redirect('/portal/hr/ta-requests/')



@login_required
def hr_ta_reject(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    app = get_object_or_404(TAApplication, pk=pk, status='TO_HR')
    if request.method == 'POST':
        note = request.POST.get('hr_note','').strip()
        app.hr_note = note
        app.status = 'REJECTED'
        app.save()
        messages.success(request, "Application rejected.")
    return redirect('/portal/hr/ta-requests/')


# ===== Casual Application via TA/UC chain =====
@login_required
def casual_apply_new(request):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    if request.method == 'POST':
        form = CasualApplicationForm(request.POST, instance=CasualApplication(applicant=request.user))
        if form.is_valid():
            app = form.save(commit=False)
            app.applicant = request.user
            recipient = form.cleaned_data.get('recipient')
            app.recipient = recipient
            if recipient and app.unit and recipient.id == app.unit.lecturer_id:
                app.status = 'TO_UC'
            else:
                app.status = 'TO_TA'
            app.save()
            messages.success(request, "Casual application submitted.")
            return redirect('/portal/casual/applications/')
    else:
        form = CasualApplicationForm(instance=CasualApplication(applicant=request.user))
    return render(request, 'timesheets/casual_apply_new.html', {'form': form})@login_required
def casual_my_apps(request):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    qs = CasualApplication.objects.filter(applicant=request.user).order_by('-created_at')
    return render(request, 'timesheets/casual_my_apps.html', {'apps': qs})

@login_required
def ta_casual_inbox(request):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    units = Unit.objects.filter(ta_assignments__user=request.user).distinct()
    qs = CasualApplication.objects.filter(unit__in=units, status='TO_TA', recipient=request.user).order_by('created_at')
    ts_items = Timesheet.objects.filter(unit__in=units, status='TO_TA', recipient=request.user).order_by('created_at')
    return render(request, 'timesheets/ta_casual_inbox.html', {'apps': qs, 'ts_items': ts_items})

@login_required
def ta_casual_forward(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_TA')
    if not TeachingAssistantAssignment.objects.filter(user=request.user, unit=app.unit).exists():
        messages.error(request, "Not authorized to forward this application.")
        return redirect('/portal/')
    if request.method == 'POST':
        note = request.POST.get('ta_note','').strip()
        app.ta_note = note
        app.status = 'TO_UC'
        app.save()
        messages.success(request, "Forwarded to Unit Coordinator.")
    return redirect('/portal/ta/casual-requests/')

@login_required
def uc_casual_inbox(request):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    units = Unit.objects.filter(lecturer=request.user)
    qs = CasualApplication.objects.filter(unit__in=units, status='TO_UC').order_by('created_at')
    return render(request, 'timesheets/uc_casual_inbox.html', {'apps': qs})

@login_required
def uc_casual_forward(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_UC')
    if app.unit.lecturer != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Not authorized.")
        return redirect('/portal/unit-coordinator/casual-requests/')
    if request.method == 'POST':
        note = request.POST.get('uc_note','').strip()
        app.uc_note = note
        app.status = 'TO_HR'
        app.save()
        messages.success(request, "Forwarded to HR.")
    return redirect('/portal/unit-coordinator/casual-requests/')

@login_required
def uc_casual_reject(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_UC')
    if app.unit.lecturer != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Not authorized.")
        return redirect('/portal/unit-coordinator/casual-requests/')
    if request.method == 'POST':
        note = request.POST.get('uc_note','').strip()
        app.uc_note = note
        app.status = 'REJECTED'
        app.save()
        messages.success(request, "Application rejected.")
    return redirect('/portal/unit-coordinator/casual-requests/')

@login_required
def hr_casual_inbox(request):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    qs = CasualApplication.objects.filter(status='TO_HR').order_by('created_at')
    return render(request, 'timesheets/hr_casual_inbox.html', {'apps': qs})

@login_required
def hr_casual_approve(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_HR')
    if request.method == 'POST':
        note = request.POST.get('hr_note','').strip()
        app.hr_note = note
        app.status = 'APPROVED'
        app.save()
        messages.success(request, "Application approved.")
    return redirect('/portal/hr/casual-requests/')

@login_required
def hr_casual_reject(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "HR only.")
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_HR')
    if request.method == 'POST':
        note = request.POST.get('hr_note','').strip()
        app.hr_note = note
        app.status = 'REJECTED'
        app.save()
        messages.success(request, "Application rejected.")
    return redirect('/portal/hr/casual-requests/')



@login_required

@login_required
def ta_ts_inbox(request):
    units = Unit.objects.filter(ta_assignments__user=request.user).distinct()
    qs = Timesheet.objects.filter(status='TO_TA', recipient=request.user, unit__in=units).select_related('tutor','unit','recipient').order_by('-created_at')
    ctx = base_ctx(request)
    ctx.update({'title': 'Timesheets — TA Inbox', 'items': qs})
    return render(request, 'timesheets/ta_ts_inbox.html', ctx)

def ta_ts_forward(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, status='TO_TA', recipient=request.user)
    if request.method == 'POST':
        comment = request.POST.get('ta_comment','').strip()
        if comment:
            ts.ta_comment = comment
            ts.save()
        ts.status = 'TO_LECT'
        ts.save()
        messages.success(request, 'Forwarded to Unit Coordinator.')
    return redirect('ta-ts-inbox')

@login_required
def ta_casual_comment(request, pk):
    if not _feature_casual_apps_enabled():
        return redirect('/portal/')
    app = get_object_or_404(CasualApplication, pk=pk, status='TO_TA', recipient=request.user)
    if request.method == 'POST':
        note = request.POST.get('ta_note','').strip()
        app.ta_note = note
        app.save(update_fields=['ta_note'])
        messages.success(request, "Comment saved.")
    return redirect('ta-casual-inbox')


@login_required
def ta_ts_comment(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, status='TO_TA', recipient=request.user)
    if request.method == 'POST':
        c = request.POST.get('ta_comment','').strip()
        ts.ta_comment = c
        ts.save()
        messages.success(request, "Comment saved.")
    return redirect('ta-ts-inbox')



@login_required
def tutor_send(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, tutor=request.user)
    if ts.status in ('DRAFT', 'REJ'):
        ts.status = 'TO_TA' if ts.route == 'TA' else 'TO_LECT'
        ts.save()
        try:
            msg = 'Sent to TA' if ts.route == 'TA' else 'Sent to unit coordinator.'
            messages.success(request, msg)
        except Exception:
            pass
    return redirect('casual-requests')



# === Unit Coordinator (Lecturer) timesheet inbox ===
@login_required
def lecturer_inbox(request):
    items = list(Timesheet.objects.filter(status='TO_LECT', unit__lecturer=request.user).order_by('id'))
    # Templates expect 'i.casual' and 'i.selected_slots'; alias tutor -> casual for display
    for i in items:
        try:
            i.casual = i.tutor
        except Exception:
            pass
    return render(request, 'timesheets/lecturer_inbox.html', {**base_ctx(request), 'items': items})

@login_required
def lecturer_courses(request):
    units = Unit.objects.filter(lecturer=request.user).order_by('code')
    return render(request, 'timesheets/lecturer_courses.html', {**base_ctx(request), 'units': units})

@login_required
def lecturer_approve(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, unit__lecturer=request.user)
    ts.status = 'TO_HR'  # forward to HR
    ts.save()
    messages.success(request, 'Forwarded to HR.')
    return redirect('lecturer-inbox')

@login_required
def lecturer_reject(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk, unit__lecturer=request.user)
    ts.status = 'REJ'
    ts.save()
    messages.success(request, 'Rejected.')
    return redirect('lecturer-inbox')

# === HR inbox for timesheets ===
@login_required
def hr_inbox(request):
    items = list(Timesheet.objects.filter(status='TO_HR').order_by('id'))
    for i in items:
        try:
            i.casual = i.tutor
        except Exception:
            pass
    return render(request, 'timesheets/hr_inbox.html', {**base_ctx(request), 'items': items})

@login_required
def hr_approve(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk)
    ts.status = 'FINAL'
    ts.save()
    messages.success(request, 'Finalized.')
    return redirect('hr-inbox')

@login_required
def hr_reject(request, pk):
    ts = get_object_or_404(Timesheet, pk=pk)
    ts.status = 'REJ'
    ts.save()
    messages.success(request, 'Rejected.')
    return redirect('hr-inbox')

@login_required

def hr_courses(request):

    # Guard: HR only
    if role(request.user) != 'HR':
        return redirect('portal-home')

    # Same-page deletion via ?delete=<id>
    delete_id = request.GET.get('delete')
    if delete_id:
        try:
            unit = Unit.objects.get(pk=int(delete_id))
            _force_delete_unit(unit)
            messages.success(request, 'Course and ALL related records were deleted.')
            return redirect('hr-courses')
        except Exception as e:
            messages.error(request, f'Force delete failed: {e}')
            return redirect('hr-courses')

    units = Unit.objects.all().order_by('code')
    return render(request, 'timesheets/hr_courses.html', {'units': units})


@login_required
def hr_course_edit(request, pk=None):
    return redirect('hr-courses')

@login_required
def hr_course_delete(request, pk):
    return redirect('hr-courses')


# ==== UC -> Casual -> HR change request flow ====
from django.contrib.auth.decorators import login_required, user_passes_test

# Fallback group_required decorator if not present
def group_required(name):
    def _dec(view_func):
        return user_passes_test(lambda u: u.is_authenticated and u.groups.filter(name__iexact=name).exists())(view_func)
    return _dec
from django.forms import ModelForm

class CasualChangeForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'new_rate' in self.fields:
            self.fields['new_rate'].widget = forms.HiddenInput()
            self.fields['new_rate'].required = False
            if not self.fields['new_rate'].initial:
                self.fields['new_rate'].initial = Decimal('50.00')

    def clean_new_rate(self):
        val = self.cleaned_data.get('new_rate')
        try:
            return val if val else Decimal('50.00')
        except Exception:
            return Decimal('50.00')

    def save(self, commit=True):
        obj = super().save(commit=False)
        try:
            if not obj.new_rate:
                obj.new_rate = Decimal('50.00')
        except Exception:
            pass
        if commit:
            obj.save()
            self.save_m2m()
        return obj
    class Meta:
        model = CasualChangeRequest
        fields = ['unit', 'casual', 'new_slots', 'new_rate']

@login_required
def uc_changes_list(request):
    if role(request.user) != 'LECT':
        return redirect('portal-home')
    qs = CasualChangeRequest.objects.filter(initiated_by=request.user).order_by('-created_at')
    return render(request, 'timesheets/uc_changes.html', {'changes': qs})

@login_required
def casual_changes_list(request):
    if role(request.user) != 'casual':
        return redirect('portal-home')
    qs = CasualChangeRequest.objects.filter(casual=request.user, status='TO_CASUAL').order_by('-created_at')
    try:
        qs = qs.prefetch_related('new_slots')
    except Exception:
        pass
    return render(request, 'timesheets/casual_changes.html', {'changes': qs})

@login_required
def uc_change_new(request):
    if role(request.user) != 'LECT':
        return redirect('portal-home')

    form = CasualChangeForm(request.POST or None)

    # Determine selected unit id (POST/GET/initial with sensible fallback)
    unit_id = None
    try:
        raw = None
        if hasattr(form, 'data'):
            raw = form.data.get('unit') or request.GET.get('unit')
        unit_id = int(raw) if raw else None
    except Exception:
        unit_id = None
    if unit_id is None:
        uq = Unit.objects.filter(lecturer=request.user).order_by('id')
        first = uq.first()
        if first:
            unit_id = first.id

    # Restrict unit choices to this UC
    form.fields['unit'].queryset = Unit.objects.filter(lecturer=request.user)

    # Ensure the Unit select keeps the chosen value after reload
    if unit_id:
        try:
            form.initial = dict(form.initial or {}, unit=unit_id)
            form.fields['unit'].initial = unit_id
        except Exception:
            pass
    # Reload with GET when unit changes so dependent fields refresh
    form.fields['unit'].widget.attrs.update({'onchange': 'window.location.href=\"?unit=\"+this.value;'})
    # Restrict new_slot strictly to the selected unit
    slots = CourseSlot.objects.filter(unit_id=unit_id) if unit_id else CourseSlot.objects.none()
    form.fields['new_slots'].queryset = slots
    # Build casual choices from FINAL timesheets on this unit (guarded)
    unit_obj = Unit.objects.filter(id=unit_id).first() if unit_id else None
    if unit_obj:
        tutor_ids = Timesheet.objects.filter(unit=unit_obj, status='FINAL').values('tutor_id')
        form.fields['casual'].queryset = User.objects.filter(id__in=Subquery(tutor_ids)).order_by('username')
    else:
        form.fields['casual'].queryset = User.objects.none()
    # Restrict casual strictly to the selected unit (via Timesheet link) — FIX: exclude TA, use Timesheet assignments only
    if unit_id:
        # Only users who have FINAL timesheets on this unit are valid 'casual' candidates
        tutor_ids = Timesheet.objects.filter(unit_id=unit_id, status='FINAL').values_list('tutor_id', flat=True)
        casual_qs = User.objects.filter(id__in=tutor_ids).distinct().order_by('username')
    else:
        casual_qs = User.objects.none()
    form.fields['casual'].queryset = casual_qs
    form.fields['casual'].empty_label = '---------'

    if request.method == 'POST':
        if form.is_valid():
            u = form.cleaned_data['unit']
            c = form.cleaned_data['casual']
            raw_sel = form.cleaned_data.get('new_slots') or form.cleaned_data.get('new_slot')
            try: sel_slots = list(raw_sel) if raw_sel is not None else []
            except Exception: sel_slots = [raw_sel] if raw_sel else []
            # Server-side validations
            if not Timesheet.objects.filter(tutor=c, unit=u).exists():
                form.add_error('casual', 'Selected casual is not assigned to this unit.')
            if sel_slots and any(getattr(slot,'unit_id',None) != u.id for slot in sel_slots):
                form.add_error('new_slots', 'New slot must belong to the selected unit.')
            if not form.errors:
                obj = form.save(commit=False)
                if not getattr(obj, 'new_rate', None):
                    obj.new_rate = Decimal('50.00')
                # ensure hourly_rate exists
                from decimal import Decimal as _D
                if getattr(obj, 'hourly_rate', None) in (None, ''):
                    obj.hourly_rate = _D('0.00')
                obj.initiated_by = request.user
                obj.status = 'TO_CASUAL'
                obj.save()
                form.save_m2m()
                messages.success(request, 'Change request sent to Casual.')
                return redirect('uc-changes')
        # if not valid, fall through to re-render with errors

    return render(request, 'timesheets/change_form.html', {
        'form': form,
        'title': 'New Change Request',
        'slots': slots
    })





@login_required
@login_required
def uc_change_send(request, pk):
    if role(request.user) != 'LECT':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, initiated_by=request.user, status='DRAFT')
    obj.status = 'TO_CASUAL'
    obj.save(update_fields=['status'])
    messages.success(request, 'Sent to casual.')
    return redirect('uc-changes')

@login_required
def uc_change_delete(request, pk):
    if role(request.user) != 'LECT':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, initiated_by=request.user, status='DRAFT')
    obj.delete()
    messages.success(request, 'Deleted.')
    return redirect('uc-changes')

def casual_change_approve(request, pk):
    if role(request.user) != 'casual':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, casual=request.user, status='TO_CASUAL')
    obj.status = 'TO_HR'
    obj.save(update_fields=['status'])
    messages.success(request, 'Approved. Sent to HR.')
    return redirect('casual-changes')

@login_required
def casual_change_reject(request, pk):
    if role(request.user) != 'casual':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, casual=request.user, status='TO_CASUAL')
    obj.status = 'REJECTED'
    obj.save(update_fields=['status'])
    messages.success(request, 'Rejected.')
    return redirect('casual-changes')

@login_required
def hr_changes_list(request):
    if role(request.user) != 'HR':
        return redirect('portal-home')
    qs = CasualChangeRequest.objects.filter(status='TO_HR').order_by('-created_at')
    try:
        qs = qs.prefetch_related('new_slots')
    except Exception:
        pass
    return render(request, 'timesheets/hr_changes.html', {'changes': qs})

@login_required
def hr_change_approve(request, pk):
    if role(request.user) != 'HR':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, status='TO_HR')
    # Apply the change to TeachingAssistantAssignment (best-effort)
    try:
        assign = TeachingAssistantAssignment.objects.filter(unit=obj.unit, user=obj.casual).first()
        if assign is not None:
            if obj.new_slot_id:
                # if there is a foreign key to slot on assignment, try common names
                if hasattr(assign, 'slot') and assign.slot_id != obj.new_slot_id:
                    assign.slot_id = obj.new_slot_id
                if hasattr(assign, 'course_slot') and assign.course_slot_id != obj.new_slot_id:
                    assign.course_slot_id = obj.new_slot_id
            if obj.new_rate is not None:
                if hasattr(assign, 'hourly_rate'):
                    assign.hourly_rate = obj.new_rate
            assign.save()
    except Exception as e:
        # non fatal: we still mark approved; UI will reflect via your own assignment listing
        pass
    obj.status = 'APPROVED'
    obj.save(update_fields=['status'])
    messages.success(request, 'Change applied.')
    return redirect('hr-changes')

@login_required
def hr_change_reject(request, pk):
    if role(request.user) != 'HR':
        return redirect('portal-home')
    obj = get_object_or_404(CasualChangeRequest, pk=pk, status='TO_HR')
    obj.status = 'REJECTED'
    obj.save(update_fields=['status'])
    messages.success(request, 'Change rejected.')
    return redirect('hr-changes')

@login_required
def uc_unit_summary(request, unit_id):

    ta_names = []  # ensure defined

    """UC 查看课程明细（仅 FINAL）：按新时薪规则汇总每位 casual 的总课时、时薪(高/低)、总薪酬。"""
    unit = get_object_or_404(Unit, id=unit_id)

    qs = (Timesheet.objects
          .filter(unit=unit, status='FINAL')
          .select_related('tutor')
          .order_by('tutor_id', 'created_at'))

    by_tutor = {}
    for ts in qs:
        rec = by_tutor.setdefault(ts.tutor_id, {
            'tutor': ts.tutor,
            'hours': Decimal('0'),
            'total_pay': Decimal('0'),
            'hourly_rate_text': '',  # 展示“高/低”
        })
        try:
            d = _policy_compute(ts)  # 已在文件中定义
            high = d.get('policy_high'); low = d.get('policy_low')
            total_hours = d.get('policy_total_hours') or Decimal('0')
            total_pay = d.get('policy_total') or Decimal('0')
            # 累加
            rec['hours'] += Decimal(str(total_hours))
            rec['total_pay'] += Decimal(str(total_pay))
            # 记录一个时薪展示文本（以最后一次为准）
            if high is not None and low is not None:
                rec['hourly_rate_text'] = f"{high:.2f} / {low:.2f}"
            # INCLUDE_MANUAL_DELTAS_POLICY
            try:
                rec['hours'] += Decimal(str(getattr(ts, 'manual_hours_delta', 0) or 0))
            except Exception:
                pass
            try:
                rec['total_pay'] += Decimal(str(getattr(ts, 'manual_pay_delta', 0) or 0))
            except Exception:
                pass

        except Exception:
            # 回退到旧字段，尽量不中断
            pay = Decimal(str(ts.total_pay or 0))
            rate = Decimal(str(ts.hourly_rate or 0))
            if rate > 0:
                rec['hours'] += (pay / rate)
            rec['total_pay'] += pay
            if not rec['hourly_rate_text'] and rate:
                rec['hourly_rate_text'] = f"{rate:.2f}"
            # INCLUDE_MANUAL_DELTAS_EXCEPT
            try:
                rec['hours'] += Decimal(str(getattr(ts, 'manual_hours_delta', 0) or 0))
            except Exception:
                pass
            try:
                rec['total_pay'] += Decimal(str(getattr(ts, 'manual_pay_delta', 0) or 0))
            except Exception:
                pass


    rows = list(by_tutor.values())
    grand_hours = sum((r['hours'] for r in rows), Decimal('0'))
    grand_pay   = sum((r['total_pay'] for r in rows), Decimal('0'))

# --- Teaching Assistants from TAApplication (Approved) ---
    try:
        from ta.models import TAApplication
        qs = TAApplication.objects.filter(unit=unit, status__in=['Approved','APPROVED'])
        tmp = []
        for app in qs:
            u = (getattr(app, 'user', None) or getattr(app, 'applicant', None) or
                 getattr(getattr(app, 'ta', None), 'user', None) or
                 getattr(getattr(app, 'casual', None), 'user', None))
            if u:
                name = (getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', None) or str(u))
                if name not in tmp:
                    tmp.append(name)
        ta_names = tmp
    except Exception:
        # keep ta_names as [] if TAApplication unavailable
        pass



    # --- Resolve TA names robustly ---
    try:
        ta_names = [] if 'ta_names' not in locals() else ta_names
    except Exception:
        ta_names = []
    # Prefer an explicit TAApplication model if available (try multiple apps / model names)
    _ta_models = []
    try:
        from ta.models import TAApplication as _TAApp
        _ta_models.append(_TAApp)
    except Exception:
        pass
    try:
        from timesheets.models import TAApplication as _TAApp2  # some deployments keep it here
        _ta_models.append(_TAApp2)
    except Exception:
        pass
    try:
        # sometimes named TaApplication
        from timesheets.models import TaApplication as _TAApp3
        _ta_models.append(_TAApp3)
    except Exception:
        pass

    collected = []
    for _Model in _ta_models:
        try:
            qs = _Model.objects.all()
            # filter by unit/course foreign key if present
            if hasattr(_Model, 'unit'):
                qs = qs.filter(unit=unit)
            elif hasattr(_Model, 'course'):
                qs = qs.filter(course=unit)
            elif hasattr(_Model, 'unit_offer'):
                qs = qs.filter(unit_offer=unit)
            # filter by approved-ish status if the field exists
            if hasattr(_Model, 'status'):
                qs = qs.filter(status__in=['Approved', 'APPROVED', 'approved', 'Accept', 'ACCEPT', 'Accepted'])
            tmp = []
            for app in qs:
                u = (getattr(app, 'user', None) or getattr(app, 'applicant', None) or
                     getattr(getattr(app, 'ta', None), 'user', None) or
                     getattr(getattr(app, 'casual', None), 'user', None))
                if u:
                    name = (getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', None) or str(u))
                    if name and name not in tmp:
                        tmp.append(name)
            collected.extend([n for n in tmp if n not in collected])
        except Exception:
            continue

    # If nothing collected, fall back to any direct relations on unit if available
    if not collected:
        direct_rel = None
        for attr in ['ta_users', 'tas', 'assistants', 'ta_list']:
            direct_rel = getattr(unit, attr, None)
            if direct_rel is not None:
                break
        if direct_rel is not None:
            try:
                users = [getattr(x, 'user', x) for x in direct_rel.all()]
            except Exception:
                users = []
            seen = set()
            for u in users:
                if not u: 
                    continue
                name = (getattr(u, 'get_full_name', lambda: '')() or getattr(u, 'username', None) or str(u))
                if name and name not in seen:
                    seen.add(name)
                    collected.append(name)

    # assign back
    if collected:
        ta_names = collected

    context = {
        'unit': unit,
        'rows': rows,
        'grand_hours': grand_hours,
        'grand_pay': grand_pay,
        'ta_names': ta_names,
        'total_budget': getattr(unit, 'budget_amount', 0),
        'used_amount': grand_pay,
        'remaining_budget': (getattr(unit, 'budget_amount', 0) - grand_pay) if getattr(unit, 'budget_amount', 0) else 0,
    }
    return render(request, 'timesheets/uc_unit_summary.html', context)

class _UserPhDModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name() or obj.username
        try:
            if hasattr(obj, 'profile') and obj.profile and obj.profile.is_phd:
                return f"{name} (PhD)"
        except Exception:
            pass
        return name

class UCHoursAdjustForm(forms.Form):
    casual = _UserPhDModelChoiceField(queryset=User.objects.none(), label="Casual")
    rate_value = forms.ChoiceField(label="Rate", choices=(), required=True)
    delta_hours = forms.DecimalField(label="Hours Δ", decimal_places=2, max_digits=7,
                                     help_text="Positive = add hours, negative = subtract. Examples: 1 or -0.5",
                                     widget=forms.NumberInput(attrs={"step": "1"}))
    note = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={'rows':3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style widgets
        if 'casual' in self.fields:
            self.fields['casual'].widget.attrs.update({'class': 'form-select'})
        if 'rate_value' in self.fields:
            self.fields['rate_value'].widget.attrs.update({'class': 'form-select'})
        if 'delta_hours' in self.fields:
            self.fields['delta_hours'].widget.attrs.update({'class': 'form-control'})
        if 'note' in self.fields:
            self.fields['note'].widget.attrs.update({'class': 'form-control'})
@login_required
def uc_adjust_hours(request, unit_id):
    # Only the lecturer (UC) of this Unit can access
    unit = get_object_or_404(Unit, id=unit_id)
        # Allow UC (lecturer of unit) OR assigned TA to access
    is_uc_ok = (role(request.user) == 'LECT' and unit.lecturer_id == request.user.id)
    try:
        from timesheets.models import TeachingAssistantAssignment
        is_ta_ok = TeachingAssistantAssignment.objects.filter(user=request.user, unit=unit).exists()
    except Exception:
        is_ta_ok = False
    if not (is_uc_ok or is_ta_ok):
        return redirect('portal-home')

    # Build candidate casual list: ONLY casuals with FINAL timesheets for this unit
    tutor_ids = list(Timesheet.objects.filter(unit=unit, status='FINAL')
                     .values_list('tutor_id', flat=True))
    ids = sorted(set(tutor_ids))
    qs_users = User.objects.filter(id__in=ids).order_by('username')

    def _choices_for_user(user):
        from decimal import Decimal
        phd = bool(getattr(getattr(user, 'profile', None), 'is_phd', False)) if user else False
        HIGH = Decimal('193.68') if phd else Decimal('162.12')
        LOW  = Decimal('129.13') if phd else Decimal('108.08')
        return [(str(HIGH), f"First-time class ({HIGH}/h)"), (str(LOW), f"Repeat class ({LOW}/h)")]

    if request.method == 'POST':
        form = UCHoursAdjustForm(request.POST)
        form.fields['casual'].queryset = qs_users
        try:
            sel_user = User.objects.filter(id=int(request.POST.get('casual'))).first()
        except Exception:
            sel_user = None
        form.fields['rate_value'].choices = _choices_for_user(sel_user)
        if form.is_valid():
            casual = form.cleaned_data['casual']
            delta_hours = Decimal(str(form.cleaned_data['delta_hours']))
            note = form.cleaned_data['note']

            ts, _ = Timesheet.objects.get_or_create(
                tutor=casual, unit=unit,
                defaults={'hourly_rate': unit.max_hourly_rate}
            )
            # Use current timesheet rate but cap at unit max if defined
            try:
                rate = Decimal(str(form.cleaned_data['rate_value']))
            except Exception:
                rate = Decimal(str(ts.hourly_rate or unit.max_hourly_rate or 0))

            delta_pay = (rate * delta_hours).quantize(Decimal('0.01'))
            # Update totals (pay only; hours remain slot-based)
            prev_pay = Decimal(str(ts.total_pay or 0))
            new_total_pay = (prev_pay + delta_pay).quantize(Decimal('0.01'))
            # (removed) do not overwrite base total_pay; use manual_*_delta instead
            # record manual deltas so summary page can reflect adjustments
            try:
                ts.manual_hours_delta = (ts.manual_hours_delta or Decimal('0')) + delta_hours
            except Exception:
                ts.manual_hours_delta = delta_hours
            try:
                ts.manual_pay_delta = (ts.manual_pay_delta or Decimal('0')) + delta_pay
            except Exception:
                ts.manual_pay_delta = delta_pay

            # Append audit note
            stamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            flag = '+' if delta_hours >= 0 else ''
            line = f"[UC adjust {stamp}] {flag}{delta_hours}h @ {rate} => {flag}${delta_pay}"
            try:
                ts.desc = (ts.desc + "\n" + line) if ts.desc else line
            except Exception:
                ts.desc = line
            ts.save()

            messages.success(request, f"Adjusted {casual.username}'s hours by {flag}{delta_hours} hour(s). Totals updated.")
            return redirect('uc-courses')
    else:
        form = UCHoursAdjustForm()
        form.fields['casual'].queryset = qs_users
        # Preselect via ?casual= and build rate choices
        try:
            pre_id = int(request.GET.get('casual')) if request.GET.get('casual') else None
        except Exception:
            pre_id = None
        pre_user = User.objects.filter(id=pre_id).first() if pre_id else qs_users.first()
        if pre_user:
            form.fields['casual'].initial = pre_user.id
        form.fields['rate_value'].choices = _choices_for_user(pre_user)

    return render(request, 'timesheets/uc_adjust_hours.html', {'unit': unit, 'form': form})


from django.http import JsonResponse

@login_required
def my_profile(request):
    user = request.user
    # Best-effort to read profile.is_phd; default False if missing
    is_phd = False
    try:
        if hasattr(user, 'profile') and user.profile:
            is_phd = bool(user.profile.is_phd)
    except Exception:
        pass

    # Basic roles (group names)
    roles = list(user.groups.values_list('name', flat=True))

    ctx = {
        "user_obj": user,
        "full_name": user.get_full_name() or user.username,
        "email": user.email,
        "roles": roles,
        "is_phd": is_phd,
    }
    return render(request, "portal/my_profile.html", ctx)

@login_required
def api_me_phd(request):
    user = request.user
    is_phd = False
    try:
        if hasattr(user, 'profile') and user.profile:
            is_phd = bool(user.profile.is_phd)
    except Exception:
        pass
    return JsonResponse({"is_phd": is_phd})

def _ta_application_units_for_user(user):
    unit_ids = set()
    for model_name in ['TAApplication', 'CasualApplication', 'TeachingAssistantApplication', 'TutorApplication']:
        try:
            M = apps.get_model('timesheets', model_name)
        except Exception:
            M = None
        if M is None:
            continue
        user_q = Q()
        field_names = {f.name for f in M._meta.fields}
        for f in ['applicant', 'user', 'tutor', 'created_by']:
            if f in field_names:
                user_q |= Q(**{f: user})
        if not user_q:
            continue
        qs = M.objects.filter(user_q)
        if 'status' in field_names:
            qs = qs.filter(status__iexact='approved')
        if 'unit' in field_names:
            unit_ids.update(qs.values_list('unit_id', flat=True))
            break
    return unit_ids


@login_required
def ta_courses(request):
    user = request.user
    unit_ids = set(
        Timesheet.objects.filter(tutor=user)
        .values_list('unit_id', flat=True).distinct()
    )
    unit_ids |= _ta_application_units_for_user(user)
    units = list(Unit.objects.filter(id__in=unit_ids).order_by('code'))
    final_set = set(
        Timesheet.objects.filter(tutor=user, status='FINAL', unit_id__in=unit_ids)
        .values_list('unit_id', flat=True).distinct()
    )
    rows = [{'u': u, 'has_final': (u.id in final_set)} for u in units]
    ctx = {**base_ctx(request), 'units': units, 'rows': rows}
    return render(request, 'timesheets/ta_courses.html', ctx)


@login_required
def ta_unit_summary(request, unit_id):
    return uc_unit_summary(request, unit_id)

@login_required
def ta_adjust_hours(request, unit_id):
    return uc_adjust_hours(request, unit_id)



@login_required
def ta_dashboard(request):
    """TA dashboard in UC-style cards.
    Shows all units where current user is a TA (either has a FINAL timesheet or has an approved TA application).
    For each unit: list slots and FINAL tutors (same as UC dashboard).
    """
    user = request.user
    # Collect unit ids from existing timesheets (any status) and approved applications
    unit_ids = set(
        Timesheet.objects.filter(tutor=user)
        .values_list('unit_id', flat=True).distinct()
    )
    unit_ids |= _ta_application_units_for_user(user)

    units = Unit.objects.filter(id__in=unit_ids).prefetch_related('slots').order_by('code')
    rows = []
    for u in units:
        slot_rows = []
        for s in u.slots.all().order_by('weekday','start_time'):
            tutors = list(
                TimesheetSlot.objects.filter(slot=s, timesheet__unit=u, timesheet__status='FINAL')
                .values_list('timesheet__tutor__username', flat=True).distinct()
            )
            slot_rows.append({'slot': s, 'tutors': tutors})
        rows.append({'unit': u, 'slots': slot_rows})
    return render(request, 'timesheets/dashboard_lecturer.html', {**base_ctx(request), 'rows': rows})



@login_required
def ta_request(request):
    if role(request.user) != 'TA':
        return redirect('tutor_requests')
    ctx = {**base_ctx(request)}
    return render(request, 'timesheets/ta_request.html', ctx)


def _user_is_hr(user):
    if getattr(user, 'is_superuser', False):
        return True
    try:
        return user.groups.filter(name__in=['hr', 'HR']).exists()
    except Exception:
        return False

@login_required
@require_http_methods(["GET", "POST"])

@login_required
@require_http_methods(["GET", "POST"])
def hr_create_account(request):
    if not _user_is_hr(request.user):
        return HttpResponseForbidden("Only HR can create accounts.")
    if request.method == "POST":
        role = (request.POST.get("role") or "").strip().lower()
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        is_phd = request.POST.get("is_phd") == "on"

        if role == "hr":
            messages.error(request, "Creating HR accounts is disabled.")
            return render(request, "timesheets/hr_create_account.html", {"role": "", "username": username, "is_phd": is_phd})

        if not role or not username or not password:
            messages.error(request, "Role / Username / Password are required.")
            return render(request, "timesheets/hr_create_account.html", {"role": role, "username": username, "is_phd": is_phd})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "timesheets/hr_create_account.html", {"role": role, "username": username, "is_phd": is_phd})

        user = User.objects.create_user(username=username, password=password)

        role_map = {"uc": "UC", "ta": "TA", "casual": "CASUAL"}
        if role in role_map:
            target = role_map[role]
            target_group, _ = Group.objects.get_or_create(name=target)
            for g in Group.objects.filter(name__in=["UC","TA","CASUAL","unit coordinator","teaching assistant","uc","ta","casual"]):
                user.groups.remove(g)
            user.groups.add(target_group)

        # --- add alias groups for cross-compatibility ---
        alias_map = {
            "UC": ["unit coordinator"],
            "TA": ["teaching assistant"],
            "CASUAL": ["casual"],  # keep lowercase alias for safety
        }
        if target in alias_map:
            for alias in alias_map[target]:
                alias_group, _ = Group.objects.get_or_create(name=alias)
                user.groups.add(alias_group)


        if role == "ta":
            try:
                from timesheets.models import TA
                ta_obj, _ = TA.objects.get_or_create(user=user)
                if hasattr(ta_obj, "is_phd"):
                    ta_obj.is_phd = is_phd
                    ta_obj.save()
            except Exception:
                pass
        if role == "casual":
            try:
                from timesheets.models import Casual
                c_obj, _ = Casual.objects.get_or_create(user=user)
                if hasattr(c_obj, "is_phd"):
                    c_obj.is_phd = is_phd
                    c_obj.save()
            except Exception:
                pass
        if role == "uc":
            try:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
            except Exception:
                pass

        messages.success(request, f"Account '{username}' created as {role}.")
        return redirect("hr_create_account")
    return render(request, "timesheets/hr_create_account.html")



@login_required
@group_required('hr')
def hr_accounts(request):
    """Show UC, TA, CASUAL users side-by-side for HR."""
    from django.contrib.auth.models import User, Group
    # Normalize aliases
    def members(names):
        qs = User.objects.none()
        for n in names:
            try:
                g = Group.objects.get(name__iexact=n)
                qs = qs | g.user_set.all()
            except Group.DoesNotExist:
                continue
        return qs.order_by('username').distinct()

    ucs = members(['UC','unit coordinator'])
    tas = members(['TA','teaching assistant'])
    casuals = members(['CASUAL','casual']).exclude(username__in=['casual_user','tutor1'])

    ctx = base_ctx(request)
    ctx.update({'ucs': ucs, 'tas': tas, 'casuals': casuals})
    return render(request, 'timesheets/hr_accounts.html', ctx)
