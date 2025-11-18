
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    dependencies = [
        ('timesheets', '0004_ta_application'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='TeachingAssistantAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ta_assignments', to='timesheets.unit')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ta_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('user', 'unit')}},
        ),
        migrations.CreateModel(
            name='CasualApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=True, verbose_name='ID')),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('TO_TA', 'Submitted to TA'), ('TO_UC', 'Submitted to Unit Coordinator'), ('TO_HR', 'Forwarded to HR'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='DRAFT', max_length=12)),
                ('note', models.TextField(blank=True)),
                ('ta_note', models.TextField(blank=True)),
                ('uc_note', models.TextField(blank=True)),
                ('hr_note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='casual_applications', to=settings.AUTH_USER_MODEL)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='casual_applications', to='timesheets.unit')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
