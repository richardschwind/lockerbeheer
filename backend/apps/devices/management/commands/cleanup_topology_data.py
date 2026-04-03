from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, F, Q

from apps.devices.models import AccessEvent, RaspberryPi
from apps.lockers.models import Locker
from apps.rentals.models import Rental
from apps.users.models import LockerUser, NFCTag


class Command(BaseCommand):
    help = 'Ruim inconsistentie/orphan data op voor locatie-locker-pi topologie.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Optioneel: ruim alleen data op voor een specifiek bedrijf.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Voer daadwerkelijk deletes uit. Zonder deze flag is het dry-run.',
        )

    def _print_count(self, label, count):
        self.stdout.write(f'{label}: {count}')

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        apply_changes = options.get('apply', False)

        self.stdout.write('Cleanup gestart (dry-run)' if not apply_changes else 'Cleanup gestart (apply)')
        if company_id:
            self.stdout.write(f'Company scope: {company_id}')

        with transaction.atomic():
            total_deleted = 0

            # 1) Lockers zonder locatie/company-context horen niet meer thuis in het model.
            lockers_qs = Locker.objects.filter(
                Q(location__isnull=True) | Q(location__company__isnull=True)
            )
            if company_id:
                lockers_qs = lockers_qs.filter(location__company_id=company_id)
            lockers_to_delete = list(lockers_qs.values_list('id', flat=True))
            self._print_count('Lockers zonder locatie/company', len(lockers_to_delete))
            if apply_changes and lockers_to_delete:
                deleted, _ = Locker.objects.filter(id__in=lockers_to_delete).delete()
                total_deleted += deleted

            # 2) LockerUsers zonder geldige website_user/company.
            locker_users_qs = LockerUser.objects.filter(
                Q(website_user__isnull=True) | Q(website_user__company__isnull=True)
            )
            if company_id:
                locker_users_qs = locker_users_qs.filter(website_user__company_id=company_id)
            locker_users_to_delete = list(locker_users_qs.values_list('id', flat=True))
            self._print_count('LockerUsers orphan', len(locker_users_to_delete))
            if apply_changes and locker_users_to_delete:
                deleted, _ = LockerUser.objects.filter(id__in=locker_users_to_delete).delete()
                total_deleted += deleted

            # 3) NFC tags zonder geldige lockergebruiker.
            nfc_qs = NFCTag.objects.filter(
                Q(locker_user__isnull=True)
                | Q(locker_user__website_user__isnull=True)
                | Q(locker_user__website_user__company__isnull=True)
            )
            if company_id:
                nfc_qs = nfc_qs.filter(locker_user__website_user__company_id=company_id)
            nfc_to_delete = list(nfc_qs.values_list('id', flat=True))
            self._print_count('NFCTags orphan', len(nfc_to_delete))
            if apply_changes and nfc_to_delete:
                deleted, _ = NFCTag.objects.filter(id__in=nfc_to_delete).delete()
                total_deleted += deleted

            # 4) Rentals met company mismatch tussen locker en lockergebruiker.
            rentals_mismatch_qs = Rental.objects.filter(locker__isnull=False).exclude(
                locker__location__company_id=F('locker_user__website_user__company_id')
            )
            if company_id:
                rentals_mismatch_qs = rentals_mismatch_qs.filter(
                    Q(locker__location__company_id=company_id)
                    | Q(locker_user__website_user__company_id=company_id)
                )
            rentals_mismatch_ids = list(rentals_mismatch_qs.values_list('id', flat=True))
            self._print_count('Rentals company mismatch', len(rentals_mismatch_ids))
            if apply_changes and rentals_mismatch_ids:
                deleted, _ = Rental.objects.filter(id__in=rentals_mismatch_ids).delete()
                total_deleted += deleted

            # 5) Dubbele actieve rentals per locker: behoud oudste, verwijder rest.
            active_rentals = Rental.objects.filter(status=Rental.Status.ACTIVE)
            if company_id:
                active_rentals = active_rentals.filter(locker__location__company_id=company_id)

            duplicate_lockers = (
                active_rentals.values('locker__id')
                .annotate(active_count=Count('id', distinct=True))
                .filter(active_count__gt=1)
            )

            duplicate_rental_ids = []
            for row in duplicate_lockers:
                rental_ids = list(
                    active_rentals.filter(locker__id=row['locker__id'])
                    .order_by('created_at', 'id')
                    .values_list('id', flat=True)
                    .distinct()
                )
                duplicate_rental_ids.extend(rental_ids[1:])

            self._print_count('Dubbele actieve rentals (te verwijderen)', len(duplicate_rental_ids))
            if apply_changes and duplicate_rental_ids:
                deleted, _ = Rental.objects.filter(id__in=duplicate_rental_ids).delete()
                total_deleted += deleted

            # 6) AccessEvents met locker die niet bij dezelfde company hoort als de Pi.
            events_mismatch_qs = AccessEvent.objects.filter(locker__isnull=False).exclude(
                locker__location__company_id=F('raspberry_pi__company_id')
            )
            if company_id:
                events_mismatch_qs = events_mismatch_qs.filter(raspberry_pi__company_id=company_id)
            events_mismatch_ids = list(events_mismatch_qs.values_list('id', flat=True))
            self._print_count('AccessEvents company mismatch', len(events_mismatch_ids))
            if apply_changes and events_mismatch_ids:
                deleted, _ = AccessEvent.objects.filter(id__in=events_mismatch_ids).delete()
                total_deleted += deleted

            # 7) Pi's zonder locatie horen niet voor te komen in nieuwe topologie.
            pis_without_location_qs = RaspberryPi.objects.filter(location__isnull=True)
            if company_id:
                pis_without_location_qs = pis_without_location_qs.filter(company_id=company_id)
            pis_without_location_ids = list(pis_without_location_qs.values_list('id', flat=True))
            self._print_count('Pi zonder locatie', len(pis_without_location_ids))
            if apply_changes and pis_without_location_ids:
                deleted, _ = RaspberryPi.objects.filter(id__in=pis_without_location_ids).delete()
                total_deleted += deleted

            if not apply_changes:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('Dry-run klaar. Geen wijzigingen opgeslagen.'))
                return

            self.stdout.write(self.style.SUCCESS(f'Cleanup voltooid. Totaal verwijderde records: {total_deleted}'))
