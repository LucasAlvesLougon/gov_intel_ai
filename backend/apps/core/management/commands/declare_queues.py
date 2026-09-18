from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kombu.exceptions import OperationalError

from config.celery import app


class Command(BaseCommand):
    help = "Declara exchanges, fila de processamento e DLQ duráveis antes do consumo."

    def handle(self, *args, **options):
        try:
            with app.connection_for_write() as connection:
                connection.ensure_connection(max_retries=3)
                with connection.channel() as channel:
                    settings.DEAD_LETTER_QUEUE(channel).declare()
                    for queue in settings.CELERY_TASK_QUEUES:
                        queue(channel).declare()
        except OperationalError:
            raise CommandError("BROKER_UNAVAILABLE") from None
        self.stdout.write("Filas duráveis declaradas.")
