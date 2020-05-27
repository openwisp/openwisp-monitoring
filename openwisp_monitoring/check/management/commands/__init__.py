from django.core.management.base import BaseCommand

from ...utils import run_checks_async


class BaseRunChecksCommand(BaseCommand):
    help = 'Run all monitoring checks asynchronously'

    def handle(self, *args, **options):
        run_checks_async()
