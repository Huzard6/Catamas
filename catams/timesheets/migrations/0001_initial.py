
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('budget_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('active', models.BooleanField(default=True)),
                ('lecturer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='units', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CourseSlot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.IntegerField(choices=[(0,'Mon'),(1,'Tue'),(2,'Wed'),(3,'Thu'),(4,'Fri'),(5,'Sat'),(6,'Sun')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slots', to='timesheets.unit')),
            ],
        ),
        migrations.CreateModel(
            name='Timesheet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('desc', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('DRAFT','Draft'),('TO_LECT','casual→unit coordinator'),('TO_HR','unit coordinator→HR'),('FINAL','Finalized'),('REJ','Rejected')], default='DRAFT', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tutor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tutor_timesheets', to=settings.AUTH_USER_MODEL)),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='timesheets', to='timesheets.unit')),
            ],
        ),
        migrations.CreateModel(
            name='TimesheetSlot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='timesheets.courseslot')),
                ('timesheet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='selected_slots', to='timesheets.timesheet')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='timesheetslot',
            unique_together={('timesheet','slot')},
        ),
    ]
