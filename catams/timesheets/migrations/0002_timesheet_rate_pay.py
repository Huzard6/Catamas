
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='hourly_rate',
            field=models.DecimalField(max_digits=7, decimal_places=2, default=50),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='total_pay',
            field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
    ]
