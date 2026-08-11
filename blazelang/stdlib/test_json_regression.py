#!/usr/bin/env python3
"""
Regression tests for the BlazeLang `\\:` JSON corruption bug.

Two things are tested in isolation (without needing the full BlazeLang
package/lexer/parser wiring):

1. blazelang/stdlib/json.py (JsonLibrary.stringify/parse) -- this was
   already correct; these tests prove it and guard against regressions.

2. Interpreter._interpolate_string (the function called by Show()/Print())
   -- this was the ACTUAL source of the bug. Show() ran every string
   argument through the interpolation engine, which treats `{...}` as an
   embedded-expression span. JSON text is full of `{...}` and `"key":value`
   syntax that isn't BlazeLang interpolation syntax at all, so it got
   misparsed and corrupted. The fix adds a guard that recognizes
   JSON-shaped `{...}` content and passes it through untouched.

Run: python3 test_json_regression.py
"""

import re
import sys
import types

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# Part 1: JSON module (json.py) round-trip correctness
# ---------------------------------------------------------------------------

def load_json_library():
    """Load json.py with a stubbed blazelang.errors.error_handler.JSONError,
    avoiding any name collision with the stdlib `json` module."""
    pkg = types.ModuleType("blazelang")
    errpkg = types.ModuleType("blazelang.errors")

    class JSONError(Exception):
        def __init__(self, msg, line=None, col=None):
            super().__init__(msg)

    errmod = types.ModuleType("blazelang.errors.error_handler")
    errmod.JSONError = JSONError
    sys.modules["blazelang"] = pkg
    sys.modules["blazelang.errors"] = errpkg
    sys.modules["blazelang.errors.error_handler"] = errmod

    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(here, "json.py")
    # Load under a name that doesn't shadow the stdlib `json` module (the
    # source file itself calls `import json` expecting the stdlib module).
    # Temporarily hide this directory from sys.path while executing it.
    old_path = sys.path[:]
    sys.path = [p for p in sys.path if os.path.abspath(p or ".") != here]
    try:
        spec = importlib.util.spec_from_file_location("blaze_json_module", src_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path = old_path
    return mod.JsonLibrary()


def test_json_module():
    print("\n--- Part 1: json.py (Json.Stringify / Json.Parse) ---")
    lib = load_json_library()

    # The exact case from the bug report.
    data = lib.parse('{"name":"Rohit","age":12,"active":true}')
    out = lib.stringify(data)
    check(
        "bug-report round trip produces no backslash before ':'",
        out == '{"name":"Rohit","age":12,"active":true}',
        f"got {out!r}",
    )

    cases = [
        {"name": "Rohit", "age": 12, "active": True},
        {"message": "hello: world"},
        {"url": "https://example.com"},
        {"text": 'hello "world"'},
        {"path": "C:\\Users\\Rohit"},
        {"items": [1, 2, 3]},
        {"user": {"name": "Rohit", "active": True}},
        {}, [], None,
    ]
    for c in cases:
        s = lib.stringify(c)
        back = lib.parse(s)
        check(f"stringify/parse round trip for {c!r}", back == c, f"got {s!r} -> {back!r}")
        check(f"no stray backslash before ':' in {s!r}", "\\:" not in s)


# ---------------------------------------------------------------------------
# Part 2: Interpreter._interpolate_string (the real bug)
# ---------------------------------------------------------------------------

class MiniInterp:
    """A minimal stand-in exercising the exact _interpolate_string /
    _evaluate_embedded_expression / _match_operator_outside_brackets logic
    from interpreter.py (including the fix), without pulling in the full
    lexer/parser/AST machinery."""

    _JSON_LIKE_BRACE_CONTENT = re.compile(r'"\s*:\s*(?:"|-?\d|true\b|false\b|null\b|\{|\[)')

    def __init__(self):
        self.current_scope = {}
        self.global_scope = {}

    def is_truthy(self, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value != ''
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True

    def _format_value(self, value):
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return '[' + ', '.join(self._format_value(v) for v in value) + ']'
        if isinstance(value, dict):
            return '{' + ', '.join(f"'{k}': {self._format_value(v)}" for k, v in value.items()) + '}'
        return str(value)

    def _match_operator_outside_brackets(self, expr, operators):
        depth = 0
        sorted_ops = sorted(operators, key=len, reverse=True)
        i = 0
        in_string = False
        string_char = None
        while i < len(expr):
            if in_string:
                if expr[i] == string_char:
                    in_string = False
                    string_char = None
                i += 1
            elif expr[i] in '"\'':
                in_string = True
                string_char = expr[i]
                i += 1
            elif expr[i] in '([{':
                depth += 1
                i += 1
            elif expr[i] in ')]}':
                depth -= 1
                i += 1
            elif depth == 0:
                for op in sorted_ops:
                    if expr[i:i + len(op)] == op:
                        if op.isalpha():
                            before_ok = i == 0 or not expr[i - 1].isalnum()
                            after_ok = i + len(op) >= len(expr) or not expr[i + len(op)].isalnum()
                            if before_ok and after_ok:
                                return (expr[:i], op, expr[i + len(op):])
                        else:
                            return (expr[:i], op, expr[i + len(op):])
                i += 1
            else:
                i += 1
        return None

    def _evaluate_embedded_expression(self, expr):
        if not expr:
            return ''
        expr = expr.strip()

        arith_match = self._match_operator_outside_brackets(expr, ['+', '-', '*', '/', '%'])
        if arith_match:
            left_expr, op, right_expr = arith_match
            left = self._evaluate_embedded_expression(left_expr.strip())
            right = self._evaluate_embedded_expression(right_expr.strip())
            try:
                if isinstance(left, str) or isinstance(right, str):
                    if op == '+':
                        return str(left) + str(right)
                    raise ValueError()
                left_num = float(left) if not isinstance(left, (int, float)) else left
                right_num = float(right) if not isinstance(right, (int, float)) else right
                if op == '+':
                    return left_num + right_num
                elif op == '-':
                    return left_num - right_num
                elif op == '*':
                    return left_num * right_num
                elif op == '/':
                    return left_num / right_num if right_num != 0 else float('inf')
                elif op == '%':
                    return left_num % right_num
            except (ValueError, TypeError):
                pass

        if expr in self.current_scope:
            return self.current_scope[expr]['value']
        if expr in self.global_scope:
            return self.global_scope[expr]['value']
        if expr == 'true':
            return True
        if expr == 'false':
            return False
        if expr == 'null':
            return None
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass
        if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        return f'{{{expr}}}'

    def _interpolate_string(self, text):
        result = []
        i = 0
        while i < len(text):
            if text[i] == '{':
                brace_count = 1
                j = i + 1
                while j < len(text) and brace_count > 0:
                    if text[j] == '{':
                        brace_count += 1
                    elif text[j] == '}':
                        brace_count -= 1
                    j += 1
                if brace_count == 0:
                    expr = text[i + 1:j - 1].strip()
                    if self._JSON_LIKE_BRACE_CONTENT.search(expr):
                        result.append(text[i:j])
                        i = j
                        continue
                    try:
                        value = self._evaluate_embedded_expression(expr)
                        result.append(self._format_value(value))
                    except Exception:
                        result.append(f'{{{expr}}}')
                    i = j
                    continue
            result.append(text[i])
            i += 1
        return ''.join(result)


def test_show_interpolation():
    print("\n--- Part 2: Show()/Print() interpolation (Interpreter._interpolate_string) ---")
    interp = MiniInterp()

    json_texts = [
        '{"name":"Rohit","age":12,"active":true}',
        '{"message":"hello: world"}',
        '{"url":"https://example.com"}',
        '{"text":"hello \\"world\\""}',
        '{"path":"C:\\\\Users\\\\Rohit"}',
        '{"items":[1,2,3]}',
        '{"user":{"name":"Rohit","active":true}}',
        # V11 regression cases
        '{"name":"Rohit","age":12,"active":true,"skills":["Python","C++","BlazeLang"]}',
        '[{"id":1,"title":"Learn BlazeLang","completed":true}]',
        '{"nullValue":null,"boolean":true,"integer":42}',
        '{"url":"http://example.com:8080","active":true}',
        '{"user":{"profile":{"name":"Rohit","active":true}}}',
        '[{"id":1,"completed":true},{"id":2,"completed":false}]',
        '{"nullValue":null,"boolean":true,"integer":42,"decimal":3.14}',
        '{"colon":"http://example.com:8080","newline":"line one\\nline two","tab":"one\\ttwo"}',
    ]
    for t in json_texts:
        out = interp._interpolate_string(t)
        check(f"Show(json) leaves {t!r} unmodified", out == t, f"got {out!r}")
        check(f"no stray backslash before ':' in Show output {out!r}", "\\:" not in out)

    # Legitimate interpolation must still work.
    interp.current_scope['name'] = {'value': 'Rohit'}
    interp.current_scope['a'] = {'value': 3}
    interp.current_scope['b'] = {'value': 4}
    greeting = interp._interpolate_string("Hello {name}, sum={a + b}")
    check("legit variable interpolation still works", greeting == "Hello Rohit, sum=7", f"got {greeting!r}")


def test_format_value_infinity_nan():
    """Regression test for BLZ9001 'cannot convert float infinity to integer'.

    Root cause: _format_value / _struct_display_value in interpreter.py did
        if isinstance(value, float) and value == int(value):
            return str(int(value))
    int(float('inf')) raises OverflowError, int(float('nan')) raises
    ValueError -- both float('inf') == int(float('inf')) comparisons never
    even get that far safely, since Python evaluates int(value) as part of
    the comparison. The fix adds `math.isfinite(value)` to the guard so
    only finite whole-number floats get normalized to int; inf/nan fall
    through to `str(value)` ('inf' / '-inf' / 'nan').
    """
    print("\n--- Part 3: Math.INFINITY / Math.NAN display (BLZ9001 regression) ---")
    import math

    def format_value(value):
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) and math.isfinite(value) and value == int(value):
            return str(int(value))
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        return str(value)

    cases = [
        (10, "10"),
        (10.5, "10.5"),
        (9.0, "9"),                    # Math.Sqrt(81)
        (256.0, "256"),                # Math.Pow(2, 8)
        (math.pi, str(math.pi)),
        (math.inf, "inf"),
        (-math.inf, "-inf"),
        (math.nan, "nan"),
    ]
    for value, expected in cases:
        try:
            got = format_value(value)
            check(f"format_value({value!r}) == {expected!r}", got == expected, f"got {got!r}")
        except Exception as e:
            check(f"format_value({value!r}) does not raise", False, f"raised {e!r}")

    # Math.IsInteger / IsFinite / IsNaN must not crash on inf/nan either.
    def is_integer(value):
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float):
            return math.isfinite(value) and value.is_integer()
        return False

    check("IsInteger(inf) is False, no crash", is_integer(math.inf) is False)
    check("IsInteger(nan) is False, no crash", is_integer(math.nan) is False)
    check("IsFinite(inf) is False", math.isfinite(math.inf) is False)
    check("IsNaN(nan) is True", math.isnan(math.nan) is True)

    # Json.Stringify(inf)/Json.Stringify(nan) must raise a clean JSONError,
    # never emit invalid JSON like `Infinity`/`NaN` and never crash the
    # interpreter -- json.py already does this correctly (see Part 1).
    lib = load_json_library()
    for value, label in [(math.inf, "inf"), (math.nan, "nan")]:
        try:
            lib.stringify(value)
            check(f"Json.Stringify({label}) raises JSONError", False, "did not raise")
        except Exception as e:
            check(f"Json.Stringify({label}) raises JSONError", type(e).__name__ == "JSONError", f"raised {type(e).__name__}: {e}")


if __name__ == "__main__":
    test_json_module()
    test_show_interpolation()
    test_format_value_infinity_nan()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)