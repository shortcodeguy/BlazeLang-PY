"""
Error handling and formatting for BlazeLang
Provides detailed error messages with source code context
"""

from typing import Optional, List
import os
import sys


class BlazeError(Exception):
    """Base exception class for all BlazeLang errors"""

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        filename: Optional[str] = None,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        note: Optional[str] = None,
    ):
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename
        self.code = code or self.default_code(message)
        self.hint = hint
        self.note = note
        self.call_stack: List[str] = []
        super().__init__(self.format_error())

    def default_code(self, message: str) -> str:
        return "BLZ2001"

    def attach_context(self, line=None, column=None, filename=None, call_stack=None):
        """Fill location details once at the point an error is observed."""
        self.line = self.line if self.line is not None else line
        self.column = self.column if self.column is not None else column
        self.filename = self.filename or filename
        if call_stack and not self.call_stack:
            self.call_stack = list(call_stack)
        self.args = (self.format_error(),)

    def format_error(self) -> str:
        """Format the error message with location information"""
        parts = []
        if self.filename:
            parts.append(self.filename)
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.column is not None:
            parts.append(f"col {self.column}")

        location = ":".join(parts)
        if location:
            return f"{self.message}\n  at {location}"
        return f"{self.message}"


# --- Syntax & Lexing Errors ---

class LexerError(BlazeError):
    """Raised when lexer encounters invalid tokens or characters"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Syntax Error: {message}",
            line,
            column,
            filename,
            code="BLZ1001",
            hint="Check for missing matching quotes, invalid special characters, or typos.",
        )


class ParserError(BlazeError):
    """Raised when parser encounters invalid syntax"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Parser Error: {message}",
            line,
            column,
            filename,
            code="BLZ1002",
            hint="Ensure all parentheses '()', brackets '[]', and braces '{}' are correctly paired and closed.",
        )


class IndentError(BlazeError):
    """Raised for indentation mismatches"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Indentation Error: {message}",
            line,
            column,
            filename,
            code="BLZ1003",
            hint="BlazeLang uses consistent spaces or tabs. Make sure your block indentation matches.",
        )


class UnexpectedTokenError(BlazeError):
    """Raised when the parser sees a token that cannot appear in the current position"""

    def __init__(self, found: str, expected: str = None, line: int = None, column: int = None, filename: str = None):
        msg = f"Unexpected token '{found}'"
        if expected:
            msg += f", expected {expected}"
        super().__init__(
            msg,
            line,
            column,
            filename,
            code="BLZ1004",
            hint="Look just before this location for a missing operator, comma, or closing symbol.",
        )


class UnterminatedError(BlazeError):
    """Raised for unterminated strings, comments, or blocks"""

    def __init__(self, construct: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Unterminated {construct}",
            line,
            column,
            filename,
            code="BLZ1005",
            hint=f"Make sure the {construct} is properly closed before the end of the file or line.",
        )


# --- Runtime Errors ---

class RuntimeError(BlazeError):
    """Raised during program execution"""

    def __init__(
        self,
        message: str,
        line: int = None,
        column: int = None,
        filename: str = None,
        code: str = "BLZ2001",
        hint: str = None,
        note: str = None,
    ):
        super().__init__(f"Runtime Error: {message}", line, column, filename, code=code, hint=hint, note=note)


class NameError(RuntimeError):
    """Raised when an undefined identifier/variable is accessed"""

    def __init__(self, var_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Undefined variable or function '{var_name}'",
            line,
            column,
            filename,
            code="BLZ2002",
            hint=f"Did you spell '{var_name}' correctly? Ensure it is defined before reading it.",
        )


class ZeroDivisionError(RuntimeError):
    """Raised when dividing or moduloing by zero"""

    def __init__(self, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            "Division by zero",
            line,
            column,
            filename,
            code="BLZ2003",
            hint="Make sure the right side of '/' or '%' cannot evaluate to zero.",
            note="Mathematically, division by zero is undefined.",
        )


class TypeError(BlazeError):
    """Raised for incompatible data type operations"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Type Error: {message}",
            line,
            column,
            filename,
            code="BLZ2004",
            hint="Check that values on both sides of an operator or function argument match expected types.",
        )


class IndexError(BlazeError):
    """Raised when accessing a list/array index that is out of bounds"""

    def __init__(self, index: int, length: int, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Index '{index}' is out of bounds for list of size {length}",
            line,
            column,
            filename,
            code="BLZ2005",
            hint=f"Valid indices range from 0 to {length - 1}." if length > 0 else "The list is currently empty.",
        )


class KeyError(BlazeError):
    """Raised when accessing a missing key in a map/dictionary"""

    def __init__(self, key: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Key Error: '{key}' not found in map",
            line,
            column,
            filename,
            code="BLZ2006",
            hint=f"Check if key '{key}' exists before reading it, or use a default getter.",
        )


class ArgumentError(BlazeError):
    """Raised when passing incorrect number or types of arguments to functions"""

    def __init__(
        self,
        func_name: str,
        expected: int,
        given: int,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"Function '{func_name}' expects {expected} argument(s), but received {given}",
            line,
            column,
            filename,
            code="BLZ2007",
            hint=f"Adjust the argument count when calling '{func_name}()'.",
        )


class AccessError(RuntimeError):
    """Raised when private/protected members are accessed from outside their owning class"""

    def __init__(self, member_name: str, class_name: str = None, line: int = None, column: int = None, filename: str = None):
        where = f" of class '{class_name}'" if class_name else ""
        super().__init__(
            f"'{member_name}'{where} is private and cannot be accessed from outside the class",
            line,
            column,
            filename,
            code="BLZ2008",
            hint="Private members are only reachable from inside their own class, e.g. via 'this'. Expose a public method instead if outside access is needed.",
        )


class PrivateVariableAccessError(RuntimeError):
    """Raised when a `private var`/`private constant` class field is read or
    written from outside its owning class. This is distinct from AccessError
    (which covers private methods and static members) so field-visibility
    violations get their own clear, specific diagnostic, as requested by the
    Variable Visibility & Null Support feature."""

    def __init__(self, variable_name: str, class_name: str = None, line: int = None, column: int = None, filename: str = None):
        where = f" of class '{class_name}'" if class_name else ""
        super().__init__(
            f"Cannot access private variable '{variable_name}'{where}",
            line,
            column,
            filename,
            code="BLZ2021",
            hint="Private variables are only reachable from inside their own class, e.g. via 'this'. Expose a public method or public variable instead if outside access is needed.",
        )


class ImmutableError(RuntimeError):
    """Raised when attempting to reassign a constant"""

    def __init__(self, name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Cannot assign to constant '{name}'",
            line,
            column,
            filename,
            code="BLZ2009",
            hint=f"'{name}' was declared with a constant/fixed declaration. Use a regular variable if it needs to change.",
        )


class NotCallableError(RuntimeError):
    """Raised when attempting to call a value that isn't a function, method, or class"""

    def __init__(self, name: str, actual_type: str = None, line: int = None, column: int = None, filename: str = None):
        type_note = f" (found {actual_type})" if actual_type else ""
        super().__init__(
            f"'{name}' is not callable{type_note}",
            line,
            column,
            filename,
            code="BLZ2010",
            hint=f"Check that '{name}' is actually a function, method, or class before calling it with '()'.",
        )


class PropertyError(RuntimeError):
    """Raised when accessing or assigning a property that doesn't exist or isn't valid on a value"""

    def __init__(self, property_name: str, target_type: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Cannot access property '{property_name}' of {target_type}",
            line,
            column,
            filename,
            code="BLZ2011",
            hint=f"Verify that '{property_name}' is actually defined on this {target_type}, and that the value isn't null.",
        )


class RecursionError(RuntimeError):
    """Raised when the call stack exceeds the maximum allowed depth"""

    def __init__(self, depth: int = None, line: int = None, column: int = None, filename: str = None):
        depth_note = f" (depth {depth})" if depth is not None else ""
        super().__init__(
            f"Maximum call stack size exceeded{depth_note}",
            line,
            column,
            filename,
            code="BLZ2012",
            hint="Check for a function that calls itself without a base case, or a loop-like recursion that never terminates.",
        )


class LoopControlError(RuntimeError):
    """Raised when 'break' or 'continue' is used outside of a loop"""

    def __init__(self, keyword: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"'{keyword}' used outside of a loop",
            line,
            column,
            filename,
            code="BLZ2013",
            hint=f"'{keyword}' can only appear inside a 'while' or 'for' loop body.",
        )


class ReturnOutsideFunctionError(RuntimeError):
    """Raised when 'return' is used outside of a function or method"""

    def __init__(self, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            "'return' used outside of a function",
            line,
            column,
            filename,
            code="BLZ2014",
            hint="'return' can only appear inside a Function, Meta, or class method body.",
        )


class InstantiationError(RuntimeError):
    """Raised when attempting to instantiate something that isn't a class"""

    def __init__(self, name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"'{name}' is not a class and cannot be instantiated",
            line,
            column,
            filename,
            code="BLZ2015",
            hint=f"Make sure '{name}' refers to a 'Class' declaration, not a function or variable.",
        )


class DuplicateDeclarationError(RuntimeError):
    """Raised when a name is declared more than once in a conflicting way"""

    def __init__(self, name: str, kind: str = "declaration", line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Duplicate {kind} '{name}'",
            line,
            column,
            filename,
            code="BLZ2016",
            hint=f"'{name}' has already been declared in this scope. Rename one of them or remove the duplicate.",
        )


class AssertionFailedError(RuntimeError):
    """Raised when an Assert() call fails"""

    def __init__(self, message: str = None, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Assertion failed{': ' + message if message else ''}",
            line,
            column,
            filename,
            code="BLZ2017",
            hint="The condition passed to Assert() evaluated to false. Check the value(s) being tested.",
        )


class NullReferenceError(RuntimeError):
    """Raised when an operation is attempted on a null value that requires a real value"""

    def __init__(self, context: str = None, line: int = None, column: int = None, filename: str = None):
        detail = f" while {context}" if context else ""
        super().__init__(
            f"Value is null{detail}",
            line,
            column,
            filename,
            code="BLZ2018",
            hint="Add a null check (e.g. 'if value != null') before using this value.",
        )


class StaticContextError(RuntimeError):
    """Raised when 'this'/'super' is used inside a static function, or an instance member is accessed via the class"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            message,
            line,
            column,
            filename,
            code="BLZ2019",
            hint="Static functions don't have access to 'this'. Use an instance method instead, or pass data in as a parameter.",
        )


class InvalidConstructorModifierError(RuntimeError):
    """Raised when a meta function (constructor) is declared with any modifier
    at all -- 'static', 'private', 'protected', or even an explicit 'public'.

    Constructors always run through Class.instantiate on a per-instance basis
    and must be reachable anywhere the class itself can be instantiated, so
    they must be written bare: 'Meta something()' with no modifier in front.
    Writing any modifier, including 'public', is rejected so the author gets
    a clear, early signal instead of the modifier being silently accepted or
    discarded.
    """

    def __init__(self, modifier: str, class_name: str = None, line: int = None, column: int = None, filename: str = None):
        where = f" in class '{class_name}'" if class_name else ""
        super().__init__(
            f"Constructor{where} cannot be declared '{modifier}'",
            line,
            column,
            filename,
            code="BLZ2020",
            hint="Constructors must be written without any modifier, e.g. 'Meta constructorName()'. "
                 f"Remove the '{modifier}' modifier from the meta function.",
        )


# --- Struct Errors ---
# Struct is a lightweight, data-only type independent of the Class system
# (see the Struct feature docs). These errors are kept separate from the
# Class-oriented errors above so a Struct-specific mistake always produces a
# clear, dedicated diagnostic instead of being folded into an unrelated
# Class/runtime error.

class DuplicateStructDeclarationError(RuntimeError):
    """Raised when a Struct is declared with a name already used by another
    Struct or Class in the same scope."""

    def __init__(self, name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"'{name}' is already declared",
            line,
            column,
            filename,
            code="BLZ2022",
            hint=f"Rename this Struct, or remove the earlier declaration of '{name}'.",
        )


class DuplicateStructFieldError(BlazeError):
    """Raised when a Struct declares the same field name more than once"""

    def __init__(self, struct_name: str, field_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Struct '{struct_name}' declares field '{field_name}' more than once",
            line,
            column,
            filename,
            code="BLZ2023",
            hint=f"Remove the duplicate '{field_name}' field from Struct '{struct_name}'.",
        )


class InvalidStructFieldError(BlazeError):
    """Raised for a malformed field declaration inside a Struct body"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Invalid Struct field: {message}",
            line,
            column,
            filename,
            code="BLZ2024",
            hint="Struct bodies contain plain fields only, e.g. 'name' or 'age = 0'.",
        )


class StructMethodNotAllowedError(BlazeError):
    """Raised when a Function/Meta declaration appears inside a Struct body"""

    def __init__(self, struct_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Struct '{struct_name}' cannot contain methods",
            line,
            column,
            filename,
            code="BLZ2025",
            hint="Struct declarations currently contain fields only. Use a Class instead if you need methods.",
        )


class StructConstructorNotAllowedError(BlazeError):
    """Raised when a Constructor/Meta constructor appears inside a Struct body"""

    def __init__(self, struct_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Struct '{struct_name}' cannot declare a constructor",
            line,
            column,
            filename,
            code="BLZ2026",
            hint="Struct construction itself initializes fields. Use a Class instead if you need custom constructor logic.",
        )


class StructInheritanceError(BlazeError):
    """Raised when a Struct attempts to inherit from anything, or a Class
    attempts to inherit from a Struct."""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Struct inheritance error: {message}",
            line,
            column,
            filename,
            code="BLZ2027",
            hint="Struct does not support inheritance in either direction. Use a Class instead if you need inheritance.",
        )


class UnknownStructFieldError(RuntimeError):
    """Raised when Struct construction is given a named argument that isn't a declared field"""

    def __init__(self, struct_name: str, field_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Struct '{struct_name}' has no field '{field_name}'",
            line,
            column,
            filename,
            code="BLZ2028",
            hint=f"Check the spelling of '{field_name}', or add it as a field on Struct '{struct_name}'.",
        )


class DuplicateStructArgumentError(RuntimeError):
    """Raised when a Struct construction call assigns the same field twice --
    either positionally and by name, or by name more than once."""

    def __init__(self, struct_name: str, field_name: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Field '{field_name}' of Struct '{struct_name}' was given a value more than once",
            line,
            column,
            filename,
            code="BLZ2029",
            hint=f"Provide '{field_name}' either positionally or by name, not both.",
        )


class StructConstructionError(RuntimeError):
    """Raised for other invalid Struct construction argument combinations,
    such as passing more positional arguments than the Struct has fields."""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            message,
            line,
            column,
            filename,
            code="BLZ2030",
            hint="Check the Struct's declared fields against the arguments passed to its constructor call.",
        )


# --- Additional Runtime Errors ---

class AttributeError(RuntimeError):
    """Raised when an object does not have the requested attribute"""

    def __init__(
        self,
        attribute_name: str,
        target_type: str = None,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        target = f"'{target_type}' object" if target_type else "value"
        super().__init__(
            f"{target} has no attribute '{attribute_name}'",
            line,
            column,
            filename,
            code="BLZ2031",
            hint=f"Check that '{attribute_name}' is defined on the target object.",
        )


class ValueError(RuntimeError):
    """Raised when a value is invalid for an operation"""

    def __init__(
        self,
        message: str,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            message,
            line,
            column,
            filename,
            code="BLZ2032",
            hint="Check that the value provided is valid for this operation.",
        )


class OverflowError(RuntimeError):
    """Raised when a numeric operation exceeds supported limits"""

    def __init__(
        self,
        message: str = "Numeric result is too large",
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            message,
            line,
            column,
            filename,
            code="BLZ2033",
            hint="Use smaller values or break the calculation into smaller operations.",
        )


class UnboundVariableError(RuntimeError):
    """Raised when a variable is accessed before being initialized"""

    def __init__(
        self,
        variable_name: str,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"Variable '{variable_name}' was accessed before it was initialized",
            line,
            column,
            filename,
            code="BLZ2034",
            hint=f"Assign a value to '{variable_name}' before reading it.",
        )


class StopIterationError(RuntimeError):
    """Raised when an iterator has no more values"""

    def __init__(
        self,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            "Iterator has no more values",
            line,
            column,
            filename,
            code="BLZ2035",
            hint="Check whether the iterator still has a value before requesting the next item.",
        )


class UnsupportedOperationError(RuntimeError):
    """Raised when an operation is unsupported for a value or type"""

    def __init__(
        self,
        operation: str,
        target_type: str = None,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        target = f" on {target_type}" if target_type else ""
        super().__init__(
            f"Operation '{operation}' is not supported{target}",
            line,
            column,
            filename,
            code="BLZ2036",
            hint="Check the operation and make sure the target value supports it.",
        )


class InvalidAssignmentError(RuntimeError):
    """Raised when an assignment target is invalid"""

    def __init__(
        self,
        target: str = None,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        target_text = f" '{target}'" if target else ""
        super().__init__(
            f"Invalid assignment target{target_text}",
            line,
            column,
            filename,
            code="BLZ2037",
            hint="Assignments must target a variable, property, or valid index.",
        )


class InvalidOperatorError(RuntimeError):
    """Raised when an operator is invalid for the supplied operands"""

    def __init__(
        self,
        operator: str,
        left_type: str = None,
        right_type: str = None,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        types = ""
        if left_type and right_type:
            types = f" between {left_type} and {right_type}"

        super().__init__(
            f"Invalid operator '{operator}'{types}",
            line,
            column,
            filename,
            code="BLZ2038",
            hint=f"Check whether '{operator}' can be used with these values.",
        )


class MissingArgumentError(RuntimeError):
    """Raised when a required function argument is missing"""

    def __init__(
        self,
        func_name: str,
        expected: int,
        given: int,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"Function '{func_name}' expects {expected} argument(s), but received {given}",
            line,
            column,
            filename,
            code="BLZ2039",
            hint=f"Provide the required argument(s) when calling '{func_name}()'.",
        )


class TooManyArgumentsError(RuntimeError):
    """Raised when too many arguments are passed to a function"""

    def __init__(
        self,
        func_name: str,
        expected: int,
        given: int,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"Function '{func_name}' expects {expected} argument(s), but received {given}",
            line,
            column,
            filename,
            code="BLZ2040",
            hint=f"Remove the extra argument(s) when calling '{func_name}()'.",
        )


# --- System & Module Errors ---

class ImportError(BlazeError):
    """Raised for module import failures"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Import Error: {message}",
            line,
            column,
            filename,
            code="BLZ3001",
            hint="Verify that the file/module path is spelled correctly and installed in the load path.",
        )


class ModuleError(BlazeError):
    """Raised for internal module export or load issues"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Module Error: {message}",
            line,
            column,
            filename,
            code="BLZ3002",
            hint="Ensure the module exports the requested symbols correctly.",
        )


class CircularImportError(ImportError):
    """Raised when modules import each other in a cycle"""

    def __init__(self, chain: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Circular import detected:\n\n{chain}",
            line,
            column,
            filename,
        )
        self.code = "BLZ3003"
        self.hint = "Break the cycle by moving the shared code into a separate module that both files import from."


class ModuleNotFoundError(ImportError):
    """Raised when an imported module cannot be found"""

    def __init__(
        self,
        module_name: str,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"No module named '{module_name}'",
            line,
            column,
            filename,
        )
        self.code = "BLZ3004"
        self.hint = (
            f"Check that module '{module_name}' exists and that its path "
            "is available to BlazeLang."
        )
        self.args = (self.format_error(),)


class ModuleLoadError(ImportError):
    """Raised when an existing module cannot be loaded"""

    def __init__(
        self,
        module_name: str,
        reason: str = None,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        detail = f": {reason}" if reason else ""

        super().__init__(
            f"Could not load module '{module_name}'{detail}",
            line,
            column,
            filename,
        )
        self.code = "BLZ3005"
        self.hint = (
            "Check that the module is valid and that all required files "
            "are available."
        )
        self.args = (self.format_error(),)


# --- Network / IO Errors ---

class HTTPError(BlazeError):
    """Raised when an HTTP request fails"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"HTTP Error: {message}",
            line,
            column,
            filename,
            code="BLZ4001",
            hint="Verify network connection, target URL, and required permissions/headers.",
        )


class TimeoutErrorBlaze(BlazeError):
    """Raised when a network or I/O operation exceeds its allotted time"""

    def __init__(self, operation: str = "operation", seconds: float = None, line: int = None, column: int = None, filename: str = None):
        time_note = f" after {seconds}s" if seconds is not None else ""
        super().__init__(
            f"Timeout: {operation} did not complete{time_note}",
            line,
            column,
            filename,
            code="BLZ4002",
            hint="Check network connectivity, or increase the timeout if the remote service is just slow.",
        )


class FileSystemError(BlazeError):
    """Raised for file reading/writing errors"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None, hint: str = None):
        super().__init__(
            f"File Error: {message}",
            line,
            column,
            filename,
            code="BLZ5001",
            hint=hint or "Check that the file path exists, is spelled right, and you have read/write access.",
        )


class FileNotFoundErrorBlaze(FileSystemError):
    """Raised when a referenced file does not exist on disk"""

    def __init__(self, path: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"File not found: '{path}'",
            line,
            column,
            filename,
            hint=f"Double check that '{path}' exists and the path is relative to the right directory.",
        )
        self.code = "BLZ5002"


class PermissionErrorBlaze(FileSystemError):
    """Raised when a file operation is denied by the OS"""

    def __init__(self, path: str, line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Permission denied: '{path}'",
            line,
            column,
            filename,
            hint=f"Check that the current user has read/write access to '{path}'.",
        )
        self.code = "BLZ5003"


class FileExistsErrorBlaze(FileSystemError):
    """Raised when attempting to create something that already exists"""

    def __init__(
        self,
        path: str,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            f"File or directory already exists: '{path}'",
            line,
            column,
            filename,
            hint=f"Choose a different path or remove the existing '{path}' first.",
        )
        self.code = "BLZ5004"
        self.args = (self.format_error(),)


class OSErrorBlaze(FileSystemError):
    """Raised for general operating-system filesystem errors"""

    def __init__(
        self,
        message: str,
        line: int = None,
        column: int = None,
        filename: str = None,
    ):
        super().__init__(
            message,
            line,
            column,
            filename,
            hint="Check the path, operating-system permissions, and filesystem state.",
        )
        self.code = "BLZ5005"
        self.args = (self.format_error(),)


class JSONError(BlazeError):
    """Raised when JSON parsing fails"""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        self.json_line = line
        self.json_column = column
        super().__init__(
            f"JSON Error: {message}",
            line,
            column,
            filename,
            code="BLZ6001",
            hint="Ensure property names are double-quoted and commas are not trailing.",
        )


class InternalInterpreterError(BlazeError):
    """Raised for internal bug state in BlazeLang engine"""

    def __init__(self, message: str = "Unexpected interpreter state.", line: int = None, column: int = None, filename: str = None):
        super().__init__(
            f"Internal Error: {message}",
            line,
            column,
            filename,
            code="BLZ9001",
            hint="This is an issue inside the BlazeLang interpreter itself. Please submit a bug report.",
        )


# --- Error Formatter ---

class ErrorFormatter:
    """Format errors with source code context and friendly beginner suggestions"""

    @staticmethod
    def format_with_snippet(error: BlazeError, source_code: str = None) -> str:
        """Format error with surrounding source code context"""
        message = str(error)

        if source_code and error.line:
            lines = source_code.splitlines()
            if 1 <= error.line <= len(lines):
                start = max(0, error.line - 2)
                end = min(len(lines), error.line + 1)

                message += "\n\n"
                for i in range(start, end):
                    line_num = i + 1
                    prefix = "> " if line_num == error.line else "  "
                    message += f"{prefix}{line_num:4} | {lines[i]}\n"

                    if line_num == error.line and error.column:
                        indent = 9 + max(0, error.column - 1)
                        message += f"{' ' * indent}^\n"

        return message

    @staticmethod
    def get_suggestion(error: BlazeError) -> str:
        """Get default fallbacks for errors missing explicit hints"""
        suggestions = {
            "LexerError": "Check for typos, missing quote marks, or unrecognized symbols.",
            "ParserError": "Check your code layout. Make sure all parentheses and brackets close.",
            "UnexpectedTokenError": "Look just before this location for a missing operator, comma, or closing symbol.",
            "UnterminatedError": "Make sure strings, comments, or blocks are properly closed.",
            "NameError": "Double-check variable name spelling or declare it before referencing.",
            "ZeroDivisionError": "Ensure the divisor value is greater or less than zero.",
            "TypeError": "Confirm the types of values being combined or passed to functions.",
            "IndexError": "Make sure your index stays within 0 and the size of your list minus 1.",
            "KeyError": "Confirm the key exists in your map before reading it.",
            "ArgumentError": "Check the function definition to see how many arguments it needs.",
            "AccessError": "Private members can only be used from inside their own class.",
            "PrivateVariableAccessError": "Private variables can only be read or written from inside their own class.",
            "ImmutableError": "Constants can't be reassigned after declaration; use a variable instead.",
            "NotCallableError": "Only functions, methods, and classes can be called with '()'.",
            "PropertyError": "Confirm the property exists on this value and the value isn't null.",
            "RecursionError": "Look for a recursive function missing a base case.",
            "LoopControlError": "'break'/'continue' only work inside a loop body.",
            "ReturnOutsideFunctionError": "'return' only works inside a function or method body.",
            "InstantiationError": "Only classes declared with 'Class' can be instantiated.",
            "DuplicateDeclarationError": "Rename or remove the conflicting declaration.",
            "AssertionFailedError": "Review the condition passed into Assert().",
            "NullReferenceError": "Add a null check before using this value.",
            "StaticContextError": "Static members can't reference 'this'; use an instance method instead.",
            "InvalidConstructorModifierError": "Constructors must be written bare, e.g. 'Meta name()' -- remove any modifier, including 'public'.",
            "IndentError": "Align your code blocks uniformly using consistent spaces.",
            "ImportError": "Ensure the file or library path is configured correctly.",
            "CircularImportError": "Break the import cycle by extracting shared code into its own module.",
            "FileSystemError": "Verify the file exists and is accessible.",
            "FileNotFoundErrorBlaze": "Double check the file path and that the file actually exists.",
            "PermissionErrorBlaze": "Check OS-level read/write permissions on the target path.",
            "TimeoutErrorBlaze": "Check connectivity, or raise the timeout if the remote end is just slow.",
            "HTTPError": "Verify the URL, network connection, and required headers/permissions.",
            "JSONError": "Ensure property names are double-quoted and commas are not trailing.",
            "DuplicateStructDeclarationError": "Rename this Struct or remove the earlier declaration.",
            "DuplicateStructFieldError": "Remove the duplicate field from the Struct declaration.",
            "InvalidStructFieldError": "Struct bodies contain plain fields only, e.g. 'name' or 'age = 0'.",
            "StructMethodNotAllowedError": "Struct declarations currently contain fields only. Use a Class instead if you need methods.",
            "StructConstructorNotAllowedError": "Struct construction itself initializes fields. Use a Class instead if you need custom constructor logic.",
            "StructInheritanceError": "Struct does not support inheritance in either direction. Use a Class instead if you need inheritance.",
            "UnknownStructFieldError": "Check the spelling of the field name, or add it to the Struct.",
            "DuplicateStructArgumentError": "Provide the field either positionally or by name, not both.",
            "StructConstructionError": "Check the Struct's declared fields against the arguments passed to its constructor call.",
            "AttributeError": "Check that the attribute exists on the target object and that its name is spelled correctly.",
            "ValueError": "Check that the value provided is valid for the operation.",
            "OverflowError": "Use smaller numeric values or split the calculation into smaller operations.",
            "UnboundVariableError": "Initialize the variable before reading its value.",
            "StopIterationError": "Check whether the iterator still contains a value before requesting the next item.",
            "UnsupportedOperationError": "Check whether this operation is supported for the target value or type.",
            "InvalidAssignmentError": "Assignments must target a variable, property, or valid index.",
            "InvalidOperatorError": "Check that the operator is valid for both operands.",
            "MissingArgumentError": "Provide all required arguments when calling the function.",
            "TooManyArgumentsError": "Remove the extra arguments from the function call.",
            "ModuleNotFoundError": "Make sure the module exists and its path is available to BlazeLang.",
            "ModuleLoadError": "Check that the module is valid and all required files are available.",
            "FileExistsErrorBlaze": "Choose a different path or remove the existing file or directory first.",
            "OSErrorBlaze": "Check the filesystem path, permissions, and operating-system state.",
        }

        error_type = type(error).__name__
        return suggestions.get(error_type, "Double check your code logic around the indicated location.")

    @staticmethod
    def format_diagnostic(error: BlazeError, source_code: str = None, color: bool = None) -> str:
        """Render a clean compiler diagnostic with ANSI color support."""
        if color is None:
            color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

        red, cyan, green, yellow, reset = (
            ("\033[91m", "\033[96m", "\033[92m", "\033[93m", "\033[0m")
            if color
            else ("", "", "", "", "")
        )

        title = f"BlazeLang [{error.code}] {type(error).__name__}"
        bar = "=" * 56
        lines = [f"{red}{bar}", title, f"{bar}{reset}", "", error.message]

        if error.filename or error.line is not None:
            lines.extend([
                "",
                f"{cyan}Location{reset}",
                f"File   : {error.filename or '<unknown>'}",
                f"Line   : {error.line if error.line is not None else '?'}",
                f"Column : {error.column if error.column is not None else '?'}",
            ])

        if source_code and error.line and 1 <= error.line <= len(source_code.splitlines()):
            source_line = source_code.splitlines()[error.line - 1]
            col = error.column or 1
            pointer = f"{' ' * (len(str(error.line)) + 3 + max(0, col - 1))}{yellow}^{reset}"
            lines.extend(["", f"{error.line} | {source_line}", pointer])

        if error.note:
            lines.extend(["", f"{cyan}Note{reset}", error.note])

        hint = error.hint or ErrorFormatter.get_suggestion(error)
        if hint:
            lines.extend(["", f"{green}Hint{reset}", hint])

        if error.call_stack:
            lines.extend(["", f"{cyan}Call Stack{reset}"] + [f"  at {frame}" for frame in error.call_stack])

        lines.append(f"{red}{bar}{reset}")
        return "\n".join(lines)