import os
import logging

from celery import Celery
from celery.signals import worker_ready

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("solara")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """
    Fires automatically the moment the Celery worker is fully started.

    Runs two tasks immediately:
      1. backfill_all  — inserts any candles missed since last shutdown
                         (e.g. weekend gap, overnight, PC was off)
      2. check_and_fix_gaps — fills any holes in stored history

    This means the DB is always brought up to date before Beat starts
    sending scheduled tasks — no manual intervention needed.
    """
    logger.info("Worker ready — triggering startup catch-up...")

    # Import here to avoid circular imports at module load time
    from ohlcv.tasks import backfill_all_ohlcv, check_and_fix_gaps

    # Chain: backfill first, then gap check
    # si() = signature with no args (immutable)
    from celery import chain
    chain(
        backfill_all_ohlcv.si(),
        check_and_fix_gaps.si(),
    ).apply_async()

    logger.info("Startup catch-up tasks queued.")
