import asyncio
import threading
import logging
from typing import Any, Callable, Coroutine

class AsyncWorker:
    """Runs an asyncio event loop in a background thread and exposes a submit method
    to schedule coroutines without calling asyncio.run from synchronous handlers.
    """
    def __init__(self):
        self._loop = None
        self._thread = None
        self._started = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        def _run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._started.set()
            try:
                self._loop.run_forever()
            except Exception as e:
                logging.exception("Async worker loop error: %s", e)

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        self._started.wait()

    def stop(self):
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=1)

    def submit(self, coro: Coroutine) -> asyncio.Future:
        if not self._loop:
            raise RuntimeError("Async worker not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)
