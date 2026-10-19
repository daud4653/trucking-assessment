from django.core.management.base import BaseCommand

from apps.route_planning.application.use_cases import purge_expired_plans


class Command(BaseCommand):
    help = "Delete route plans past their retention period."

    def handle(self, *args, **options) -> None:
        deleted = purge_expired_plans()
        self.stdout.write(f"Deleted {deleted} expired route plan(s).")
