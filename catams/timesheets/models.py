from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

WEEKDAYS=[(0,'Mon'),(1,'Tue'),(2,'Wed'),(3,'Thu'),(4,'Fri'),(5,'Sat'),(6,'Sun')]

class Unit(models.Model):
    code=models.CharField(max_length=20, unique=True)
    name=models.CharField(max_length=200)
    lecturer=models.ForeignKey(User, on_delete=models.PROTECT, related_name='units', limit_choices_to={'groups__name__iexact':'unit coordinator'})
    start_date=models.DateField()
    end_date=models.DateField()
    budget_amount=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_hourly_rate=models.DecimalField(max_digits=7, decimal_places=2, default=80)
    active=models.BooleanField(default=True)
    def __str__(self): return f"{self.code} - {self.name}"

class CourseSlot(models.Model):
    unit=models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='slots')
    weekday=models.IntegerField(choices=WEEKDAYS)
    start_time=models.TimeField()
    end_time=models.TimeField()
    class Meta:
        ordering=['weekday','start_time']
        unique_together=('unit','weekday','start_time','end_time')
    def __str__(self):
        try:
            st = self.start_time.strftime('%H:%M')
            et = self.end_time.strftime('%H:%M')
        except Exception:
            st = str(self.start_time)
            et = str(self.end_time)
        return f"{self.get_weekday_display()} {st}–{et}"



class Timesheet(models.Model):
    ROUTE=[('UC','Unit Coordinator'),('TA','Teaching Assistant')]
    STATUS=[('DRAFT','Draft'),('TO_TA','Sent to TA'),('TO_LECT','casual→unit coordinator'),('TO_HR','unit coordinator→HR'),('FINAL','Finalized'),('REJ','Rejected')]
    tutor=models.ForeignKey(User, on_delete=models.PROTECT, related_name='tutor_timesheets')
    unit=models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='timesheets')
    desc=models.TextField(blank=True)
    ta_comment=models.TextField(blank=True)
    hourly_rate=models.DecimalField(max_digits=7, decimal_places=2, default=50)
    total_pay=models.DecimalField(max_digits=12, decimal_places=2, default=0)
    manual_hours_delta=models.DecimalField(max_digits=7, decimal_places=2, default=0)
    manual_pay_delta=models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status=models.CharField(max_length=10, choices=STATUS, default='DRAFT')
    route=models.CharField(max_length=3, choices=ROUTE, default='UC')
    recipient=models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='received_timesheets')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"TS#{self.pk} {self.unit.code} by {self.tutor.username}"

class TimesheetSlot(models.Model):
    timesheet=models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='selected_slots')
    slot=models.ForeignKey(CourseSlot, on_delete=models.PROTECT)
    class Meta: unique_together=('timesheet','slot')

# === Teaching Assistant Application ===
class TAApplication(models.Model):
    STATUS = [
        ('DRAFT','Draft'),
        ('TO_UC','Submitted to Unit Coordinator'),
        ('TO_HR','Forwarded to HR'),
        ('APPROVED','Approved'),
        ('REJECTED','Rejected'),
    ]
    applicant = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ta_applications')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='ta_applications')
    status = models.CharField(max_length=12, choices=STATUS, default='DRAFT')
    note = models.TextField(blank=True)            # applicant's note
    uc_note = models.TextField(blank=True)         # UC recommendation / comment
    hr_note = models.TextField(blank=True)         # HR comment
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('applicant', 'unit', 'status')

    def __str__(self):
        ucode = getattr(self.unit, 'code', '?') if getattr(self, 'unit_id', None) else '?'
        uname = getattr(self.applicant, 'username', '?') if getattr(self, 'applicant_id', None) else '?'
        return f"TAApp#{self.pk} {ucode} by {uname} [{self.status}]"


class TeachingAssistantAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ta_assignments')
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='ta_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'unit')
    def __str__(self):
        return f"TAAssign({self.user.username} -> {self.unit.code})"


class CasualApplication(models.Model):
    recipient = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='casual_received')
    SEND_TO = [('TA','To Teaching Assistant'), ('UC','To Unit Coordinator')]
    STATUS = [
        ('DRAFT','Draft'),
        ('TO_TA','Submitted to TA'),
        ('TO_UC','Submitted to Unit Coordinator'),
        ('TO_HR','Forwarded to HR'),
        ('APPROVED','Approved'),
        ('REJECTED','Rejected'),
    ]
    applicant = models.ForeignKey(User, on_delete=models.PROTECT, related_name='casual_applications')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='casual_applications')
    status = models.CharField(max_length=12, choices=STATUS, default='DRAFT')
    note = models.TextField(blank=True)
    ta_note = models.TextField(blank=True)
    uc_note = models.TextField(blank=True)
    hr_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"CasualApp#{self.pk} {self.unit.code} by {self.applicant.username} [{self.status}]"
    class Meta:
        ordering = ['-created_at']



# === UC→Casual→HR change request for slot & hourly rate ===
class CasualChangeRequest(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('TO_CASUAL', 'Waiting for Casual'),
        ('TO_HR', 'Waiting for HR'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='change_requests')
    casual = models.ForeignKey(User, on_delete=models.CASCADE, related_name='change_requests')
    # We store ids so we are not tightly coupled if slot rows are deleted
    current_slot = models.ForeignKey(CourseSlot, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    new_slot = models.ForeignKey(CourseSlot, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    new_slots = models.ManyToManyField(CourseSlot, blank=True, related_name='+')
    old_rate = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    new_rate = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_change_requests')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    casual_note = models.CharField(max_length=255, blank=True, default='')
    hr_note = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"Change {self.unit.code} / {self.casual.username} -> {self.get_status_display()}"
    def apply_to_timesheet(self):
        from django.apps import apps
        from decimal import Decimal
        from datetime import datetime, date
        Timesheet = apps.get_model('timesheets', 'Timesheet')
        TimesheetSlot = apps.get_model('timesheets', 'TimesheetSlot')
        CourseSlot = apps.get_model('timesheets', 'CourseSlot')

        # 1) ensure a timesheet exists
        ts, _ = Timesheet.objects.get_or_create(
            tutor=self.casual,
            unit=self.unit,
            defaults={'hourly_rate': self.new_rate or Decimal('0')}
        )

        # 2) update hourly rate if provided
        if self.new_rate is not None:
            ts.hourly_rate = self.new_rate

        # 3) update selected slot: replace existing with new one
        if self.new_slot_id:
            TimesheetSlot.objects.filter(timesheet=ts).delete()
            try:
                slot = CourseSlot.objects.get(pk=self.new_slot_id)
                TimesheetSlot.objects.get_or_create(timesheet=ts, slot=slot)
            except CourseSlot.DoesNotExist:
                pass

        # 4) recompute total_pay from selected slots and capped rate
        rate = Decimal(str(ts.hourly_rate))
        try:
            cap = Decimal(str(self.unit.max_hourly_rate))
            if rate > cap:
                rate = cap
        except Exception:
            pass

        weekly_hours = Decimal('0')
        for sel in TimesheetSlot.objects.filter(timesheet=ts).select_related('slot'):
            s = sel.slot
            try:
                dt0 = datetime.combine(date.min, s.start_time)
                dt1 = datetime.combine(date.min, s.end_time)
                secs = (dt1 - dt0).total_seconds()
                if secs > 0:
                    weekly_hours += (Decimal(str(secs)) / Decimal('3600'))
            except Exception:
                pass

        days = (self.unit.end_date - self.unit.start_date).days
        weeks = (days + 6) // 7 if days >= 0 else 0
        total = (weekly_hours * Decimal(str(weeks)) * rate).quantize(Decimal('0.01'))
        ts.total_pay = total
        ts.save()

    def save(self, *args, **kwargs):
        from decimal import Decimal as _D
        if getattr(self, 'hourly_rate', None) in (None, ''):
            self.hourly_rate = _D('0.00')
        prev = None
        if self.pk:
            try:
                prev = type(self).objects.only('status').get(pk=self.pk).status
            except type(self).DoesNotExist:
                prev = None
        super().save(*args, **kwargs)
        if self.status == 'APPROVED' and prev != 'APPROVED':
            try:
                self.apply_to_timesheet()
            except Exception:
                pass



# === Multi-slot apply_to_timesheet override ===
def _ccr_apply_to_timesheet_multi(self):
    from django.apps import apps
    from decimal import Decimal
    from datetime import datetime, date
    Timesheet = apps.get_model('timesheets', 'Timesheet')
    TimesheetSlot = apps.get_model('timesheets', 'TimesheetSlot')
    CourseSlot = apps.get_model('timesheets', 'CourseSlot')

    # ensure a TS exists
    ts, _ = Timesheet.objects.get_or_create(
        tutor=self.casual,
        unit=self.unit,
        defaults={'hourly_rate': self.new_rate or Decimal('0')}
    )

    # update hourly rate with cap
    if self.new_rate is not None:
        rate = Decimal(str(self.new_rate))
        try:
            cap = Decimal(str(self.unit.max_hourly_rate))
            if rate > cap:
                rate = cap
        except Exception:
            pass
        ts.hourly_rate = rate

    # replace slots from new_slots (fallback to single new_slot)
    try:
        TimesheetSlot.objects.filter(timesheet=ts).delete()
    except Exception:
        pass
    used = False
    try:
        for s in self.new_slots.all():
            TimesheetSlot.objects.get_or_create(timesheet=ts, slot=s)
            used = True
    except Exception:
        used = False
    if not used and getattr(self, 'new_slot_id', None):
        try:
            TimesheetSlot.objects.get_or_create(timesheet=ts, slot=self.new_slot)
        except Exception:
            pass

    # recompute total pay: sum weekly hours * number of weeks * capped rate
    def _slot_hours(slot):
        try:
            st = datetime.combine(date.today(), slot.start_time)
            et = datetime.combine(date.today(), slot.end_time)
            secs = (et - st).total_seconds()
            return Decimal(str(secs)) / Decimal('3600')
        except Exception:
            return Decimal('0')
    try:
        weeks = (self.unit.end_date - self.unit.start_date).days
        weeks = max(0, weeks) // 7 + 1
    except Exception:
        weeks = 0
    per_week = Decimal('0')
    try:
        for ss in ts.selected_slots.select_related('slot').all():
            per_week += _slot_hours(ss.slot)
    except Exception:
        pass
    hours = (per_week * Decimal(str(weeks)))
    try:
        rate = Decimal(str(ts.hourly_rate))
    except Exception:
        rate = Decimal('0')
    base_pay = (rate * hours).quantize(Decimal('0.01'))
    # Preserve UC Adjust Hours effects recorded in ts.desc lines like "[UC adjust ...] +1h @ 50 => +$50.00"
    adj_sum = Decimal('0.00')
    try:
        import re as _re
        if ts.desc:
            for line in ts.desc.splitlines():
                m = _re.search(r"=>\s*([+-])?\$([0-9]+(?:\.[0-9]{2})?)", line)
                if m:
                    sign = -1 if m.group(1) == '-' else 1
                    val = Decimal(m.group(2))
                    adj_sum += (val * sign)
    except Exception:
        pass
    ts.total_pay = (base_pay + adj_sum).quantize(Decimal('0.01'))
    ts.save(update_fields=['hourly_rate','total_pay'])




class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_phd = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile({self.user.username})"


try:
    CasualChangeRequest.apply_to_timesheet = _ccr_apply_to_timesheet_multi
except Exception:
    pass


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            UserProfile.objects.get_or_create(user=instance)
        except Exception:
            pass

