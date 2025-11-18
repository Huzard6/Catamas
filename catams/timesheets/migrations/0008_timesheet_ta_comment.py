from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0007_timesheet_route_recipient'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='ta_comment',
            field=models.TextField(blank=True),
        ),
    ]
