"""BlazeLang JSON standard-library namespace."""

import json
import math

from blazelang.errors.error_handler import JSONError

# StructInstance is resolved lazily (see _struct_instance_type) rather than
# imported at module load time. blazelang.interpreter.interpreter only pulls
# this module in lazily too, inside Interpreter._import_json, specifically so
# neither module has to import the other eagerly -- importing StructInstance
# up top here would reintroduce that cycle at package-load time.
_STRUCT_INSTANCE_TYPE = None


def _struct_instance_type():
    """Resolve blazelang.interpreter.interpreter.StructInstance on first use.

    Deferred so this module never depends on the interpreter module being
    importable at *load* time -- only once JSON serialization actually runs,
    by which point the interpreter has necessarily already been imported by
    whatever is running the program. The resolved class is cached after the
    first successful lookup.
    """
    global _STRUCT_INSTANCE_TYPE
    if _STRUCT_INSTANCE_TYPE is None:
        from blazelang.interpreter.interpreter import StructInstance
        _STRUCT_INSTANCE_TYPE = StructInstance
    return _STRUCT_INSTANCE_TYPE


def _normalise(value):
    """Convert BlazeLang runtime values into JSON-compatible built-ins."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise JSONError("Cannot serialize non-finite number")
    if isinstance(value, list):
        return [_normalise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, _struct_instance_type()):
        # A Struct instance becomes a plain JSON object built from its
        # declared fields, in declaration order (StructInstance.properties
        # is populated in that order by StructType.instantiate). Reuses this
        # same recursive normaliser for each field's value, so nested
        # Structs, arrays, and objects inside a Struct all serialize the
        # same way they would anywhere else.
        return {str(key): _normalise(item) for key, item in value.properties.items()}
    return value


class JsonLibrary:
    """JSON parse, serialization, validation, and formatting operations."""

    def parse(self, text):
        # HTTP already decodes declared JSON response bodies; accepting those
        # values keeps Json.Parse(response.body) natural and backwards-safe.
        if isinstance(text, (dict, list, int, float, bool)) or text is None:
            return text
        try:
            return json.loads(str(text))
        except json.JSONDecodeError as error:
            raise JSONError("Invalid JSON: " + error.msg, error.lineno, error.colno)

    def stringify(self, value):
        try:
            return json.dumps(_normalise(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as error:
            raise JSONError(f"Cannot serialize value: {error}")

    def pretty(self, value):
        try:
            parsed = self.parse(value) if isinstance(value, str) else value
            return json.dumps(_normalise(parsed), ensure_ascii=False, indent=4, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise JSONError(f"Cannot format JSON: {error}")

    def validate(self, text):
        if not isinstance(text, str):
            return isinstance(text, (dict, list, int, float, bool)) or text is None
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, TypeError, ValueError):
            return False


def create_json_module():
    library = JsonLibrary()
    return {"Parse": library.parse, "Stringify": library.stringify,
            "Pretty": library.pretty, "Validate": library.validate}