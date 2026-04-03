# Generated migration to revert multi-locker rental back to single locker

from django.db import migrations, models
import django.db.models.deletion


def copy_m2m_back_to_fk(apps, schema_editor):
    """Copy first locker from m2m table back to locker FK"""
    Rental = apps.get_model('rentals', 'Rental')
    through_model = apps.get_model('rentals', 'Rental_lockers')

    for rental in Rental.objects.iterator():
        first_link = through_model.objects.filter(rental_id=rental.id).order_by('id').first()
        if first_link:
            rental.locker_id = first_link.locker_id
            rental.save(update_fields=['locker_id'])


def reverse_copy(apps, schema_editor):
    """Reverse: copy from FK back to m2m"""
    Rental = apps.get_model('rentals', 'Rental')
    through_model = apps.get_model('rentals', 'Rental_lockers')

    through_rows = []
    for rental in Rental.objects.exclude(locker_id__isnull=True).iterator():
        through_rows.append(
            through_model(rental_id=rental.id, locker_id=rental.locker_id)
        )

    if through_rows:
        through_model.objects.bulk_create(through_rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0002_rental_lockers_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='rental',
            name='locker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rentals',
                to='lockers.locker',
                verbose_name='Locker',
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(copy_m2m_back_to_fk, reverse_copy),
        migrations.AlterField(
            model_name='rental',
            name='locker',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='rentals',
                to='lockers.locker',
                verbose_name='Locker',
            ),
        ),
        migrations.RemoveField(
            model_name='rental',
            name='lockers',
        ),
    ]
