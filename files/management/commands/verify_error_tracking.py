"""Exercise the staging web and Celery error-tracking integrations."""

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from files.tasks import add_two

DIAGNOSTIC_URL = "http://127.0.0.1/internal/observability/error-probe"
MAX_REPEAT = 50
TASK_TIMEOUT_SECONDS = 60


class Command(BaseCommand):
    help = "Send fixed staging-only failures through the web and long-task paths"

    def add_arguments(self, parser):
        parser.add_argument("--repeat", type=int, default=1, help="Number of web failures to send (1-50)")

    def handle(self, *args, **options):
        if not getattr(settings, "ERROR_TRACKING_DIAGNOSTICS_ENABLED", False):
            raise CommandError("error tracking diagnostics are disabled")
        if getattr(settings, "SENTRY_ENVIRONMENT", "") != "staging":
            raise CommandError("error tracking diagnostics are restricted to staging")
        token = getattr(settings, "ERROR_TRACKING_DIAGNOSTICS_TOKEN", "")
        if not token:
            raise CommandError("ERROR_TRACKING_DIAGNOSTICS_TOKEN is required")
        if not getattr(settings, "SENTRY_DSN", "").strip():
            raise CommandError("SENTRY_DSN is required")

        repeat = options["repeat"]
        if repeat < 1 or repeat > MAX_REPEAT:
            raise CommandError("--repeat must be between 1 and 50")

        for _ in range(repeat):
            self._send_web_failure(token)

        task = add_two.delay(1, "diagnostic")
        try:
            result = task.get(timeout=TASK_TIMEOUT_SECONDS, propagate=False)
        except CeleryTimeoutError as error:
            raise CommandError("diagnostic Celery task timed out") from error
        except Exception as error:
            error_type = type(error).__name__
            raise CommandError(f"diagnostic Celery result lookup failed with {error_type}") from error

        if not isinstance(result, TypeError):
            if isinstance(result, BaseException):
                error_type = type(result).__name__
                raise CommandError(f"diagnostic Celery task failed with unexpected {error_type}")
            raise CommandError("diagnostic Celery task unexpectedly succeeded")

        self.stdout.write(f"web_requests={repeat} celery_task_id={task.id}")

    def _send_web_failure(self, token):
        request = Request(  # noqa: S310 - the URL is a module constant on loopback
            DIAGNOSTIC_URL,
            data=b"",
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - request URL is fixed above
                status = response.status
        except HTTPError as error:
            status = error.code
        except URLError as error:
            raise CommandError(f"diagnostic request failed: {error.reason}") from error

        if status != 500:
            raise CommandError(f"diagnostic request expected HTTP 500, received {status}")
