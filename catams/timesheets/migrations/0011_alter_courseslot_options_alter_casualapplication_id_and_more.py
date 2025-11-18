from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0010_manual_deltas_on_timesheet'),
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=r'''
                    CREATE TABLE IF NOT EXISTS "timesheets_userprofile" (
                        "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        "is_phd" bool NOT NULL DEFAULT 0,
                        "user_id" integer NOT NULL UNIQUE
                    );
                    ''',
                    reverse_sql=r'''DROP TABLE IF EXISTS "timesheets_userprofile";'''
                )
            ],
            state_operations=[
                migrations.CreateModel(
                    name='UserProfile',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('is_phd', models.BooleanField(default=False)),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
                    ],
                ),
            ],
        ),
    ]