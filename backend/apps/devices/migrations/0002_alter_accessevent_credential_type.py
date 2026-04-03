from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accessevent',
            name='credential_type',
            field=models.CharField(
                choices=[('nfc', 'NFC-tag'), ('pin', 'PIN-code'), ('system', 'Systeem')],
                max_length=20,
            ),
        ),
    ]
