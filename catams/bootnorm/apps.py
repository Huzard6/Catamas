
from django.apps import AppConfig

class BootnormConfig(AppConfig):
    name = "bootnorm"
    verbose_name = "Boot Normalizer"

    def ready(self):
        self._ensure_demo_groups()
        self._patch_forms()
        self._patch_hr_course_edit()

        
    def _ensure_demo_groups(self):
        try:
            from django.contrib.auth.models import Group
            from django.contrib.auth import get_user_model
            U = get_user_model()

            # Ensure groups exist
            groups = ['unit coordinator', 'hr', 'casual', 'teaching assistant']
            for gname in groups:
                Group.objects.get_or_create(name=gname)

            # Mapping of users to groups
            mapping = {
                'unit coordinator': ['unit_coordinator','lecturer_a','uc_1','uc_2'],
                'hr': ['hr'],
                'casual': ['casual_debug1','casual_debug2']
                , 'teaching assistant': ['ta_debug'],
            }

            for gname, users in mapping.items():
                try:
                    group = Group.objects.get(name=gname)
                except Group.DoesNotExist:
                    continue
                for uname in users:
                    try:
                        u = U.objects.get(username=uname)
                        if not u.groups.filter(name__iexact=gname).exists():
                            u.groups.add(group)
                    except U.DoesNotExist:
                        pass
        except Exception as e:
            print('Warning: ensure_demo_groups failed:', e)

    # ------------------ forms helpers ------------------
    def _patch_forms(self):
        try:
            from importlib import import_module
            from django import forms as djforms
            from django.contrib.auth import get_user_model
        except Exception:
            return

        try:
            mod = import_module('timesheets.forms')
        except Exception:
            return

        User = get_user_model()

        def wrap_form_cls(cls):
            if not isinstance(cls, type):
                return cls
            try:
                from django.forms import BaseForm
                if not issubclass(cls, BaseForm):
                    return cls
            except Exception:
                return cls

            orig_init = cls.__init__

            def __init__(self, *args, **kwargs):
                req_tutor = kwargs.pop('tutor', None) or kwargs.pop('casual', None)
                req_lect  = kwargs.pop('lecturer', None) or kwargs.pop('unit_coordinator', None)

                self._bootnorm_requesters = {}
                if req_tutor is not None:
                    self._bootnorm_requesters['tutor'] = req_tutor
                if req_lect is not None:
                    self._bootnorm_requesters['lecturer'] = req_lect

                orig_init(self, *args, **kwargs)

                # lock requester fields if present
                try:
                    for field, u in getattr(self, "_bootnorm_requesters", {}).items():
                        if hasattr(self, "fields") and field in self.fields and u is not None:
                            self.fields[field].initial = u
                            try:
                                self.fields[field].queryset = User.objects.filter(pk=getattr(u, 'pk', u))
                            except Exception:
                                pass
                            try:
                                self.fields[field].widget = djforms.HiddenInput()
                            except Exception:
                                pass
                except Exception:
                    pass

                # widen unit dropdown for TimesheetCreateForm if empty
                try:
                    if cls.__name__ == "TimesheetCreateForm" and hasattr(self, "fields") and "unit" in self.fields:
                        qs = getattr(self.fields["unit"], "queryset", None)
                        widen = (qs is None)
                        try:
                            if hasattr(qs, "exists") and not qs.exists():
                                widen = True
                        except Exception:
                            widen = True
                        if widen:
                            from timesheets.models import Unit
                            self.fields["unit"].queryset = Unit.objects.all().order_by("code")
                except Exception:
                    pass

                # UnitForm: list all users as candidates for UC
                try:
                    if cls.__name__ == "UnitForm" and hasattr(self, "fields") and "lecturer" in self.fields:
                        try:
                            from django.contrib.auth import get_user_model
                            U = get_user_model()
                        except Exception:
                            U = User
                        # restrict to UC role only, do not widen
                        self.fields["lecturer"].queryset = U.objects.filter(groups__name__iexact="unit coordinator").order_by("username")
                except Exception:
                    pass

            cls.__init__ = __init__

            if hasattr(cls, "save"):
                orig_save = cls.save
                def save(self, commit=True):
                    obj = orig_save(self, commit=False)
                    try:
                        for field, u in getattr(self, "_bootnorm_requesters", {}).items():
                            if u is not None and hasattr(obj, field):
                                if getattr(obj, field, None) in (None, ''):
                                    setattr(obj, field, u)
                    except Exception:
                        pass
                    if commit:
                        obj.save()
                        try:
                            self.save_m2m()
                        except Exception:
                            pass
                    return obj
                cls.save = save
            return cls

        try:
            for name in dir(mod):
                obj = getattr(mod, name)
                wrapped = wrap_form_cls(obj)
                if wrapped is not obj:
                    setattr(mod, name, wrapped)
        except Exception:
            return

    # ------------------ view helper ------------------
    def _patch_hr_course_edit(self):
        try:
            from importlib import import_module
            from django.apps import apps as djapps
            from django.forms import inlineformset_factory
            from django.shortcuts import render, redirect, get_object_or_404
            from django.contrib import messages
        except Exception:
            return

        try:
            vp = import_module('timesheets.views_portal')
            models = import_module('timesheets.models')
            forms = import_module('timesheets.forms')
        except Exception:
            return

        # Resolve Unit model
        Unit = getattr(models, 'Unit', None)
        if Unit is None:
            try:
                Unit = djapps.get_model('timesheets', 'Unit')
            except Exception:
                Unit = None
        if Unit is None:
            return  # can't patch without Unit

        # Resolve Slot / WeeklySlot model dynamically
        Slot = None
        # common names
        for name in ['Slot', 'WeeklySlot', 'UnitSlot', 'WeekSlot', 'Schedule']:
            Slot = getattr(models, name, None)
            if Slot is not None:
                break
        # scan all models for one related to Unit & having typical fields
        if Slot is None:
            try:
                for mdl in djapps.get_app_config('timesheets').get_models():
                    rel_to_unit = any(
                        getattr(f, 'remote_field', None) and getattr(f.remote_field, 'model', None) == Unit
                        for f in mdl._meta.get_fields()
                    )
                    has_times = all(
                        any(f.name == n for f in mdl._meta.get_fields())
                        for n in ('weekday', 'start_time', 'end_time')
                    )
                    if rel_to_unit and has_times:
                        Slot = mdl
                        break
            except Exception:
                Slot = None

        # If still not found, give up cleanly (don't break startup)
        if Slot is None:
            return

        UnitForm = getattr(forms, 'UnitForm', None)
        SlotForm = getattr(forms, 'SlotForm', None)
        if not UnitForm or not SlotForm:
            return

        SlotFS = inlineformset_factory(Unit, Slot, form=SlotForm, extra=0, can_delete=True)

        def patched(request, unit_id=None):
            unit = None
            if unit_id:
                try:
                    unit = get_object_or_404(Unit, pk=unit_id)
                except Exception:
                    unit = None

            form = UnitForm(request.POST or None, instance=unit)
            formset = SlotFS(request.POST or None, instance=unit)

            if request.method == 'POST':
                if form.is_valid() and formset.is_valid():
                    unit = form.save()
                    formset.instance = unit
                    formset.save()
                    try:
                        messages.success(request, 'Course saved.')
                    except Exception:
                        pass
                    try:
                        return redirect('hr-courses')
                    except Exception:
                        return redirect('/portal/hr/courses/')
                # else: fall-through to render with validation errors

            ctx = {'form': form, 'slot_formset': formset, 'title': 'New Course' if unit is None else 'Edit Course'}
            try:
                return render(request, 'timesheets/hr_course_edit.html', ctx)
            except Exception:
                return render(request, 'hr_course_edit.html', ctx)

        try:
            vp.hr_course_edit = patched
        except Exception:
            pass
