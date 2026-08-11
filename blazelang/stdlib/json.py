"""BlazeLang JSON standard-library namespace.

Provides JSON parsing, serialization, validation, and pretty-printing
for BlazeLang runtime values, with lazy resolution of StructInstance
to avoid import cycles.
"""

import json
import math
from typing import Any, Union, Optional, Dict, List, Set, Tuple

from blazelang.errors.error_handler import JSONError

# Lazy-loaded StructInstance class (resolved on first use)
_STRUCT_INSTANCE_TYPE = None


def _struct_instance_type():
    """Resolve StructInstance lazily and cache it."""
    global _STRUCT_INSTANCE_TYPE
    if _STRUCT_INSTANCE_TYPE is None:
        from blazelang.interpreter.interpreter import StructInstance
        _STRUCT_INSTANCE_TYPE = StructInstance
    return _STRUCT_INSTANCE_TYPE


def _normalise(value: Any) -> Any:
    """Convert BlazeLang runtime values into JSON‑compatible built‑ins.

    Raises JSONError for non‑serializable types or non‑finite numbers.
    """
    # None, bool, int, float, str are natively supported by json.dumps,
    # but we need to handle infinity/NaN and convert integer floats.
    if value is None:
        return None

    # bool must be checked before int because bool is a subclass of int
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            if not math.isfinite(value):
                raise JSONError("Cannot serialize non‑finite number")
        return value

    if isinstance(value, str):
        return value

    # Convert sequences (list, tuple, set) to JSON arrays
    if isinstance(value, (list, tuple, set)):
        return [_normalise(item) for item in value]

    # Convert dicts (including custom subclasses) to JSON objects
    if isinstance(value, dict):
        return {str(key): _normalise(val) for key, val in value.items()}

    # Handle BlazeLang Struct instances
    struct_type = _struct_instance_type()
    if struct_type is not None and isinstance(value, struct_type):
        # Structs become plain objects using declared properties
        return {str(key): _normalise(val) for key, val in value.properties.items()}

    # Unsupported type – raise early with a clear message
    raise JSONError(f"Cannot serialize value of type {type(value).__name__}")


class JsonLibrary:
    """JSON operations for BlazeLang."""

    def parse(self, text: Any) -> Any:
        """Parse a JSON string or bytes into BlazeLang values.

        If text is already a parsed JSON value (dict, list, etc.), it is
        returned as‑is. Otherwise, it must be str or bytes.
        """
        # Already a JSON‑compatible value
        if isinstance(text, (dict, list, int, float, bool)) or text is None:
            return text

        # Accept both str and bytes (and bytearray)
        if isinstance(text, (str, bytes, bytearray)):
            try:
                return json.loads(text)
            except json.JSONDecodeError as error:
                raise JSONError(f"Invalid JSON: {error.msg}", error.lineno, error.colno)

        raise JSONError(f"Expected string or bytes, got {type(text).__name__}")

    def stringify(self, value: Any) -> str:
        """Convert a BlazeLang value to a compact JSON string."""
        try:
            normalised = _normalise(value)
            return json.dumps(
                normalised,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False
            )
        except (TypeError, ValueError) as error:
            # json.dumps can raise these for unsupported types;
            # _normalise already raises JSONError for unsupported types,
            # so this catches any remaining issues.
            raise JSONError(f"Cannot serialize value: {error}")

    def pretty(self, value: Union[str, Any]) -> str:
        """Format JSON with indentation for readability."""
        try:
            # If value is a string, parse it first; otherwise treat as already parsed
            if isinstance(value, str):
                parsed = self.parse(value)
            else:
                parsed = value
            normalised = _normalise(parsed)
            return json.dumps(
                normalised,
                ensure_ascii=False,
                indent=4,
                allow_nan=False
            )
        except (TypeError, ValueError) as error:
            # Only json.dumps failures are caught; parse errors (JSONError) propagate
            raise JSONError(f"Cannot format JSON: {error}")

    def validate(self, text: Any) -> bool:
        """Check whether text is valid JSON or a JSON‑compatible value."""
        if not isinstance(text, str):
            # Non‑string values are valid if they are JSON‑compatible types
            return isinstance(text, (dict, list, int, float, bool)) or text is None
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, TypeError, ValueError):
            return False


def create_json_module() -> Dict[str, Any]:
    """Create the JSON module API as a dict of bound methods."""
    library = JsonLibrary()
    return {
        "Parse": library.parse,
        "Stringify": library.stringify,
        "Pretty": library.pretty,
        "Validate": library.validate,
    }