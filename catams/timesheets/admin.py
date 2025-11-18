from django.contrib import admin
from .models import Unit, CourseSlot, Timesheet, TimesheetSlot
class CourseSlotInline(admin.TabularInline):
    model=CourseSlot; extra=1
@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display=('code','name','lecturer','start_date','end_date','active')
    inlines=[CourseSlotInline]
class TimesheetSlotInline(admin.TabularInline):
    model=TimesheetSlot; extra=0
@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display=('id','tutor','unit','status','created_at')
    inlines=[TimesheetSlotInline]

try:
    admin.site.register(UserProfile)
except Exception:
    pass
