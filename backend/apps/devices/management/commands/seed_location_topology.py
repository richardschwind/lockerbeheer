from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.devices.models import RaspberryPi
from apps.lockers.models import Locker, LockerLocation
from apps.users.models import Company


class Command(BaseCommand):
    help = (
        'Maak een standaard topologie aan: company -> locaties -> lockers + Raspberry Pi(s) per locatie.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            required=True,
            help='ID van het bedrijf waarvoor de topologie wordt aangemaakt.',
        )
        parser.add_argument(
            '--locations',
            type=int,
            default=2,
            help='Aantal locaties om aan te maken (default: 2).',
        )
        parser.add_argument(
            '--lockers-per-location',
            type=int,
            default=20,
            help='Aantal lockers per locatie (default: 20).',
        )
        parser.add_argument(
            '--pis-per-location',
            type=int,
            default=1,
            help='Aantal Raspberry Pi\'s per locatie (default: 1).',
        )
        parser.add_argument(
            '--location-prefix',
            type=str,
            default='Locatie',
            help='Naam-prefix voor locaties (default: "Locatie").',
        )
        parser.add_argument(
            '--pi-prefix',
            type=str,
            default='Pi',
            help='Naam-prefix voor Raspberry Pi\'s (default: "Pi").',
        )
        parser.add_argument(
            '--start-locker-number',
            type=int,
            default=1,
            help='Startnummer voor locker-nummering (default: 1).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Toon wat aangemaakt zou worden zonder op te slaan.',
        )

    def _next_unique_pi_code(self, company_id, location_id, pi_index):
        base = f'pi-c{company_id}-l{location_id}-n{pi_index}'
        code = base
        suffix = 1
        while RaspberryPi.objects.filter(unique_code=code).exists():
            code = f'{base}-{suffix}'
            suffix += 1
        return code

    def handle(self, *args, **options):
        company_id = options['company_id']
        location_count = options['locations']
        lockers_per_location = options['lockers_per_location']
        pis_per_location = options['pis_per_location']
        location_prefix = options['location_prefix']
        pi_prefix = options['pi_prefix']
        next_locker_number = options['start_locker_number']
        dry_run = options['dry_run']

        if location_count < 1:
            raise CommandError('--locations moet minimaal 1 zijn.')
        if lockers_per_location < 0:
            raise CommandError('--lockers-per-location mag niet negatief zijn.')
        if pis_per_location < 0:
            raise CommandError('--pis-per-location mag niet negatief zijn.')

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist as exc:
            raise CommandError(f'Company met id {company_id} bestaat niet.') from exc

        self.stdout.write(
            f'Topologie voor company "{company.name}" (id={company.id}) - '
            f'locaties={location_count}, lockers/locatie={lockers_per_location}, pi/locatie={pis_per_location}'
        )

        def seed():
            nonlocal next_locker_number

            created_locations = 0
            created_lockers = 0
            created_pis = 0

            for loc_idx in range(1, location_count + 1):
                location_name = f'{location_prefix} {loc_idx}'
                location, loc_created = LockerLocation.objects.get_or_create(
                    company=company,
                    name=location_name,
                )
                if loc_created:
                    created_locations += 1

                self.stdout.write(f'- Locatie: {location.name} (id={location.id})')

                for _ in range(lockers_per_location):
                    locker_number = str(next_locker_number)
                    next_locker_number += 1

                    locker, locker_created = Locker.objects.get_or_create(
                        location=location,
                        number=locker_number,
                        defaults={
                            'status': Locker.Status.AVAILABLE,
                        },
                    )

                    if not locker_created and locker.location_id != location.id:
                        locker.location = location
                        locker.save(update_fields=['location'])

                    if locker_created:
                        created_lockers += 1

                for pi_idx in range(1, pis_per_location + 1):
                    pi_name = f'{pi_prefix} {location.name} #{pi_idx}'
                    existing_pi = RaspberryPi.objects.filter(company=company, name=pi_name).first()
                    if existing_pi:
                        if existing_pi.location_id != location.id:
                            existing_pi.location = location
                            existing_pi.save(update_fields=['location'])
                        continue

                    unique_code = self._next_unique_pi_code(company.id, location.id, pi_idx)
                    RaspberryPi.objects.create(
                        company=company,
                        location=location,
                        name=pi_name,
                        unique_code=unique_code,
                        is_active=True,
                    )
                    created_pis += 1

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Seed voltooid.'))
            self.stdout.write(f'Nieuwe locaties: {created_locations}')
            self.stdout.write(f'Nieuwe lockers: {created_lockers}')
            self.stdout.write(f'Nieuwe Pi\'s: {created_pis}')

        if dry_run:
            with transaction.atomic():
                seed()
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('Dry-run actief: rollback uitgevoerd.'))
            return

        seed()
