"""Tiny fire-and-forget runner for slow outbound API calls.

USSD and payment callbacks must answer quickly, so STK pushes and airtime
disbursements run in a daemon thread. Set BACKGROUND_TASKS_INLINE=True (tests)
to run them synchronously instead.
"""

import logging
import threading
import time

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)


def run_in_background(func, *args, delay=0):
    if getattr(settings, 'BACKGROUND_TASKS_INLINE', False):
        func(*args)
        return

    def runner():
        try:
            if delay:
                time.sleep(delay)
            func(*args)
        except Exception:
            logger.exception('Background task %s failed', func.__name__)
        finally:
            close_old_connections()

    threading.Thread(target=runner, daemon=True).start()
