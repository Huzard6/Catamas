
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets','0002_timesheet_rate_pay'),
    ]

    operations = [
        migrations.AddField(
            model_name='unit',
            name='max_hourly_rate',
            field=models.DecimalField(max_digits=7, decimal_places=2, default=80),
        ),
    ]
