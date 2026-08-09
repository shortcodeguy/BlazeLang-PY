"""BlazeLang mathematical functions and constants."""

import math
from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


def _number(value, name="value"):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlazeRuntimeError(f"Math.{name} must be a number")
    return value


class MathLibrary:
    def abs(self, value): return abs(_number(value))
    def sqrt(self, value):
        value = _number(value)
        if value < 0: raise BlazeRuntimeError("Math.Sqrt cannot use a negative number")
        return math.sqrt(value)
    def pow(self, base, exponent): return math.pow(_number(base, "base"), _number(exponent, "exponent"))
    def sin(self, value): return math.sin(_number(value))
    def cos(self, value): return math.cos(_number(value))
    def tan(self, value): return math.tan(_number(value))
    def log(self, value): return math.log(_number(value))
    def log10(self, value): return math.log10(_number(value))
    def exp(self, value): return math.exp(_number(value))
    def floor(self, value): return math.floor(_number(value))
    def ceil(self, value): return math.ceil(_number(value))
    def round(self, value, digits=0): return round(_number(value), int(_number(digits, "digits")))
    def min(self, *values): return min(_number(value) for value in values)
    def max(self, *values): return max(_number(value) for value in values)
    def clamp(self, value, minimum, maximum):
        value, minimum, maximum = _number(value), _number(minimum, "minimum"), _number(maximum, "maximum")
        if minimum > maximum: raise BlazeRuntimeError("Math.Clamp minimum cannot exceed maximum")
        return max(minimum, min(value, maximum))


def create_math_module():
    library = MathLibrary()
    return {"PI": math.pi, "E": math.e, "Abs": library.abs, "Sqrt": library.sqrt,
            "Pow": library.pow, "Sin": library.sin, "Cos": library.cos, "Tan": library.tan,
            "Log": library.log, "Log10": library.log10, "Exp": library.exp,
            "Floor": library.floor, "Ceil": library.ceil, "Round": library.round,
            "Min": library.min, "Max": library.max, "Clamp": library.clamp}
