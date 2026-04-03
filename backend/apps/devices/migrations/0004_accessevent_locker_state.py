from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0003_rework_pi_location_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessevent',
            name='locker_state',
            field=models.CharField(
                choices=[
                    ('free', 'Vrij'),
                    ('occupied_pin', 'Bezet via PIN'),
                    ('occupied_nfc', 'Bezet via NFC'),
                    ('opened_and_released', 'Geopend en vrijgegeven'),
                    ('conflict', 'Conflict'),
                    ('unknown', 'Onbekend'),
                ],
                default='unknown',
                max_length=32,
                verbose_name='Lockerstatus (Pi)',
            ),
        ),
        migrations.AddIndex(
            model_name='accessevent',
            index=models.Index(fields=['locker_state', '-pi_timestamp'], name='devices_acc_locker__486186_idx'),
        ),
    ]
