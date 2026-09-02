from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        'Relabel django_migrations rows from app "local" to "district" '
        'after renaming the Django app package. Idempotent and safe on fresh databases.'
    )

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM django_migrations WHERE app = %s",
                ['local'],
            )
            count = cursor.fetchone()[0]
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No local migration rows to relabel.'))
                return

            cursor.execute(
                "UPDATE django_migrations SET app = %s WHERE app = %s",
                ['district', 'local'],
            )
            self.stdout.write(
                self.style.SUCCESS(f'Relabeled {count} django_migrations row(s) from local to district.')
            )
