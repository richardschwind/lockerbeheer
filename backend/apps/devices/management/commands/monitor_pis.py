from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.devices.models import RaspberryPi


class Command(BaseCommand):
    help = 'Monitor Raspberry Pi connection status en update offline status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=600,
            help='Seconden zonder sync voordat Pi als offline wordt gemarkeerd (default: 600s/10min)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Uitgebreide output',
        )

    def handle(self, *args, **options):
        timeout_seconds = options['timeout']
        verbose = options['verbose']

        now = timezone.now()
        cutoff_time = now - timedelta(seconds=timeout_seconds)

        # Vind Pi's die te lang niet gesynchroniseerd hebben
        offline_pis = RaspberryPi.objects.filter(
            is_active=True,
            status__in=[RaspberryPi.Status.ONLINE, RaspberryPi.Status.ERROR],
            last_sync__lt=cutoff_time
        )

        count = 0
        for pi in offline_pis:
            pi.status = RaspberryPi.Status.OFFLINE
            pi.save(update_fields=['status'])
            count += 1

            if verbose:
                time_since = (now - pi.last_sync).total_seconds() / 60
                self.stdout.write(
                    self.style.WARNING(
                        f'[{pi.name}] Gemarkeerd als OFFLINE (geen sync sinds {time_since:.0f} minuten)'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {count} Pi(\'s) gemarkeerd als offline'
            )
        )

        # Optioneel: statistieken
        online = RaspberryPi.objects.filter(status=RaspberryPi.Status.ONLINE).count()
        offline = RaspberryPi.objects.filter(status=RaspberryPi.Status.OFFLINE).count()
        error = RaspberryPi.objects.filter(status=RaspberryPi.Status.ERROR).count()

        self.stdout.write(f'\nStatus overzicht:')
        self.stdout.write(self.style.SUCCESS(f'  Online: {online}'))
        self.stdout.write(self.style.WARNING(f'  Offline: {offline}'))
        self.stdout.write(self.style.ERROR(f'  Error: {error}'))
