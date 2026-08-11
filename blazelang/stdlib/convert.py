"""
Convert module for BlazeLang
Provides explicit numeric/string conversion utilities so language
primitives (like Input(), which always returns a String) can be
converted into numeric types on demand.

Follows the same module-factory convention as the other stdlib
modules (create_math_module, create_random_module, ...): a single
create_convert_module() function returning a plain dict of
name -> callable, consumed by Interpreter._import_standard_module.
"""

import re

from blazelang.errors.error_handler import TypeError as BlazeTypeError
from blazelang.errors.error_handler import OverflowError as BlazeOverflowError

INT32_MIN = -2147483648
INT32_MAX = 2147483647
INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807

# Matches an optional sign followed by digits only (surrounding
# whitespace is stripped before this check). Strict: no decimal
# point, no exponent, no thousands separators.
_INT_PATTERN = re.compile(r'^[+-]?\d+$')

# Matches a plain decimal float: optional sign, digits, optional
# '.' + digits. No exponent notation, to keep behavior predictable
# and consistent with the strict-integer rule above.
_FLOAT_PATTERN = re.compile(r'^[+-]?(\d+\.\d*|\.\d+|\d+)$')


def _coerce_int_string(value, target_name: str) -> int:
    """Turn a String or numeric value into a Python int for one of the
    fixed-width integer conversions. Strict: rejects decimals like
    '12.5' rather than truncating them, and rejects non-numeric text."""
    if isinstance(value, bool):
        # Booleans are technically ints in Python; BlazeLang treats
        # them as their own type, so route them through True/False
        # -> 1/0 explicitly rather than letting isinstance(int) below
        # accidentally accept them.
        return 1 if value else 0

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if value != int(value):
            raise BlazeTypeError(
                f"Cannot convert {value} to {target_name}: value has a fractional "
                f"part. Use Convert.ToFloat() instead, or pass a whole number."
            )
        return int(value)

    if isinstance(value, str):
        text = value.strip()
        if not text or not _INT_PATTERN.match(text):
            raise BlazeTypeError(
                f"Cannot convert \"{value}\" to {target_name}: not a valid integer."
            )
        return int(text)

    raise BlazeTypeError(
        f"Cannot convert value of type {type(value).__name__} to {target_name}."
    )


def to_int32(value) -> int:
    """Convert value to a signed 32-bit integer."""
    result = _coerce_int_string(value, "Int32")
    if result < INT32_MIN or result > INT32_MAX:
        raise BlazeOverflowError(
            f"Value {result} is out of range for Int32 "
            f"({INT32_MIN} to {INT32_MAX})."
        )
    return result


def to_int64(value) -> int:
    """Convert value to a signed 64-bit integer."""
    result = _coerce_int_string(value, "Int64")
    if result < INT64_MIN or result > INT64_MAX:
        raise BlazeOverflowError(
            f"Value {result} is out of range for Int64 "
            f"({INT64_MIN} to {INT64_MAX})."
        )
    return result


def to_float(value) -> float:
    """Convert value to a floating point number."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        text = value.strip()
        if not text or not _FLOAT_PATTERN.match(text):
            raise BlazeTypeError(
                f"Cannot convert \"{value}\" to Float: not a valid number."
            )
        return float(text)

    raise BlazeTypeError(
        f"Cannot convert value of type {type(value).__name__} to Float."
    )


def to_string(value) -> str:
    """Convert value to its BlazeLang string representation."""
    # Imported lazily to avoid a module-load-time circular import between
    # interpreter.py and stdlib modules (interpreter.py imports stdlib
    # modules lazily inside its _import_* methods for the same reason).
    from blazelang.interpreter.interpreter import _struct_display_value
    return _struct_display_value(value)


def create_convert_module() -> dict:
    """Factory returning the Convert module's exported members."""
    return {
        'ToInt32': to_int32,
        'ToInt64': to_int64,
        'ToFloat': to_float,
        'ToString': to_string,
    }