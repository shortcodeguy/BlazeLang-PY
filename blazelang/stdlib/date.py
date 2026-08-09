"""Local calendar helpers for BlazeLang."""

from datetime import date


class DateLibrary:
    def _today(self): return date.today()
    def today(self): return self._today().isoformat()
    def year(self): return self._today().year
    def month(self): return self._today().month
    def day(self): return self._today().day
    def weekday(self): return self._today().strftime("%A")
    def format(self, pattern):
        pattern = str(pattern)
        replacements = {"yyyy": "%Y", "MM": "%m", "dd": "%d", "HH": "%H", "mm": "%M", "ss": "%S"}
        for token, directive in replacements.items(): pattern = pattern.replace(token, directive)
        return self._today().strftime(pattern)


def create_date_module():
    library = DateLibrary()
    return {"Today": library.today, "Year": library.year, "Month": library.month,
            "Day": library.day, "Weekday": library.weekday, "Format": library.format}
