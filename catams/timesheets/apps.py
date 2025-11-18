from django.apps import AppConfig
class TimesheetsConfig(AppConfig):
    default_auto_field='django.db.models.BigAutoField'
    name='timesheets'

    def ready(self):
        try:
            from . import signals_patch_phd  # noqa: F401
        except Exception:
            pass
