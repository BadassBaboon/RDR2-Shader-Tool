"""Background worker thread queue for non-blocking UI tasks."""

import queue
import sys
import threading
import traceback
from typing import Any, Callable, Optional


class Tasks:
    """Dispatches slow I/O or compiler subprocesses in background threads."""

    def __init__(self, root, on_busy: Optional[Callable[[bool, str], None]] = None, on_log: Optional[Callable[[str], None]] = None):
        self.root = root
        self.on_busy = on_busy
        self.on_log = on_log
        self.q = queue.Queue()
        self._check_queue()

    def run(self, func: Callable, args=(), kwargs=None, done: Optional[Callable[[Any], None]] = None, label: str = "working..."):
        if self.on_busy:
            self.on_busy(True, label)
        if self.on_log:
            self.on_log(f"Starting task: {label}")

        kwargs = kwargs or {}

        def worker():
            try:
                res = func(*args, **kwargs)
                self.q.put((done, res, None, label))
            except Exception as ex:
                self.q.put((done, None, ex, label))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _check_queue(self):
        try:
            while True:
                done, res, err, label = self.q.get_nowait()
                if self.on_busy:
                    self.on_busy(False, "")

                if err:
                    if self.on_log:
                        self.on_log(f"Error in {label}: {err}")
                    print(f"Task error ({label}): {err}", file=sys.stderr)
                elif done:
                    done(res)
        except queue.Empty:
            pass

        self.root.after(50, self._check_queue)
