from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0004_accessevent_locker_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='raspberrypi',
            name='last_whitelist_ack_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Laatste whitelist bevestiging'),
        ),
    ]