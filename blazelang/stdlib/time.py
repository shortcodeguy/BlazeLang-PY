"""Local clock and sleep helpers for BlazeLang."""

import time as clock
from datetime import datetime
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


class TimeLibrary:
    def _now(self): return datetime.now()
    def now(self): return self._now().strftime("%H:%M:%S")
    def hour(self): return self._now().hour
    def minute(self): return self._now().minute
    def second(self): return self._now().second
    def sleep(self, milliseconds):
        try: milliseconds = float(milliseconds)
        except (TypeError, ValueError): raise BlazeRuntimeError("Time.Sleep requires milliseconds as a number")
        if milliseconds < 0: raise BlazeRuntimeError("Time.Sleep cannot use a negative duration")
        clock.sleep(milliseconds / 1000)


def create_time_module():
    library = TimeLibrary()
    return {"Now": library.now, "Hour": library.hour, "Minute": library.minute,
            "Second": library.second, "Sleep": library.sleep}
