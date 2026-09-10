import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Recurring content generation runs once a day.
GENERATE_INTERVAL_SECONDS = 24 * 60 * 60


class CalendarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.calendar"
    verbose_name = "Content Calendar"

    def ready(self):
        from django.db.models.signals import post_migrate

        # Register the daily recurrence-generation task with
        # django-background-tasks. ``post_migrate`` guarantees the task table
        # exists before we touch it; mirrors apps/publisher/apps.py and
        # apps/analytics/apps.py.
        post_migrate.connect(self._register_recurring_task, sender=self)

    @staticmethod
    def _register_recurring_task(sender, **kwargs):
        """Idempotently register the daily content-generation cron."""
        from apps.calendar.tasks import run_recurring_posts_cycle
        from apps.common.background import register_recurring_task

        register_recurring_task(
            run_recurring_posts_cycle,
            repeat=GENERATE_INTERVAL_SECONDS,
            verbose_name="generate_recurring_posts",
        )
