from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lockers', '0003_move_company_to_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='locker',
            name='status',
            field=models.CharField(
                choices=[
                    ('available', 'Beschikbaar'),
                    ('occupied', 'Bezet (algemeen)'),
                    ('occupied_pin', 'Bezet via PIN'),
                    ('occupied_nfc', 'Bezet via NFC'),
                    ('maintenance', 'Onderhoud'),
                    ('reserved', 'Gereserveerd'),
                ],
                default='available',
                max_length=20,
            ),
        ),
    ]
