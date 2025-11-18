from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0008_timesheet_ta_comment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CasualChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ('new_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ('status', models.CharField(default='DRAFT', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('casual_note', models.CharField(blank=True, default='', max_length=255)),
                ('hr_note', models.CharField(blank=True, default='', max_length=255)),
                ('casual', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_requests', to=settings.AUTH_USER_MODEL)),
                ('initiated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='initiated_change_requests', to=settings.AUTH_USER_MODEL)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_requests', to='timesheets.unit')),
                ('current_slot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='timesheets.courseslot')),
                ('new_slot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='timesheets.courseslot')),
            ],
        ),
        migrations.AddField(
            model_name='casualchangerequest',
            name='new_slots',
            field=models.ManyToManyField(blank=True, related_name='+', to='timesheets.courseslot'),
        ),
    ]
