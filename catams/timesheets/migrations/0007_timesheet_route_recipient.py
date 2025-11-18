from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [
        ('timesheets', '0006_casual_recipient'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='route',
            field=models.CharField(choices=[('UC','Unit Coordinator'),('TA','Teaching Assistant')], default='UC', max_length=3),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='recipient',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='received_timesheets', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='timesheet',
            name='status',
            field=models.CharField(choices=[('DRAFT','Draft'),('TO_TA','Sent to TA'),('TO_LECT','Sent to Unit Coordinator'),('TO_HR','Sent to HR'),('FINAL','Finalized'),('REJ','Rejected')], default='DRAFT', max_length=10),
        ),
    ]