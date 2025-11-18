from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0009_casualchangerequest_new_slots'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='manual_hours_delta',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='manual_pay_delta',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
