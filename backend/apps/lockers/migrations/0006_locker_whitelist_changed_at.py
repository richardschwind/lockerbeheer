from django.db import migrations, models


def backfill_whitelist_changed_at(apps, schema_editor):
    Locker = apps.get_model('lockers', 'Locker')
    for locker in Locker.objects.all().iterator():
        locker.whitelist_changed_at = locker.updated_at
        locker.save(update_fields=['whitelist_changed_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('lockers', '0005_alter_locker_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='locker',
            name='whitelist_changed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_whitelist_changed_at, migrations.RunPython.noop),
    ]