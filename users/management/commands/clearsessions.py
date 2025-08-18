"""
Django management command to clear expired sessions.
Run this periodically in production to clean up old session data.

Usage:
    python manage.py clearsessions

Can be added to cron job for automatic cleanup:
    0 2 * * * cd /path/to/project && python manage.py clearsessions
"""

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Clear expired sessions from the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        expired_sessions = Session.objects.filter(expire_date__lt=now)
        count = expired_sessions.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would delete {count} expired sessions")
            )
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No expired sessions to clean up"))
            return

        expired_sessions.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {count} expired sessions")
        )
