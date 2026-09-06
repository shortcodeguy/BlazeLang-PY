"""
Tree-walking interpreter for BlazeLang
Executes the AST by visiting each node
"""

from blazelang.ast.ast_nodes import *
from blazelang.errors.error_handler import (
    RuntimeError as BlazeRuntimeError,
    ImportError as BlazeImportError,
    TypeError as BlazeTypeError,
    BlazeError,
    AccessError,
    ImmutableError,
    NotCallableError,
    PropertyError,
    LoopControlError,
    ReturnOutsideFunctionError,
    InstantiationError,
    ZeroDivisionError as BlazeZeroDivisionError,
    StaticContextError,
    CircularImportError,
    InvalidConstructorModifierError,
    PrivateVariableAccessError,
    UnknownStructFieldError,
    DuplicateStructArgumentError,
    StructConstructionError,
    StructInheritanceError,
    IndexError as BlazeIndexError,
    DuplicateEnumValueError,
    EnumValueNotFoundError,
    ArgumentError,
    NativeModuleError,
    ValueError as BlazeValueError,
    InvalidBindDeclarationError,
    BindMetadataAccessError,
    InvalidBindAssignmentError,
    UnsupportedBindOperationError,
    InvalidBindStateError,
    InvalidAwaitError,
    ReflectExpectedFieldError,
    ReflectSourceTypeError,
    EvalDepthExceededError,
)
from typing import Any, Callable, Dict, List
import re
import math
from pathlib import Path
import os
from datetime import datetime
from difflib import get_close_matches
from builtins import ValueError as PyValueError
from blazelang.stdlib.tensor import Tensor
from blazelang.stdlib.persistence import build_localstorage_namespaces
import blazelang.stdlib.video
import blazelang.stdlib.image


# Module-level tables are created once, not for every binary expression.
_BINARY_OPERATORS = {
    '-': lambda a, b: a - b, '*': lambda a, b: a * b,
    '/': lambda a, b: a / b, '%': lambda a, b: a % b,
    '**': lambda a, b: a ** b, '^': lambda a, b: a ** b,
    '==': lambda a, b: a == b, '!=': lambda a, b: a != b,
    '>': lambda a, b: a > b, '<': lambda a, b: a < b,
    '>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b,
}
_NO_FAST_PATH = object()


class ReturnException(Exception):
    """Exception to handle return statements"""
    def __init__(self, value=None):
        self.value = value


class BreakException(Exception):
    """Exception to handle break statements"""
    pass


class ContinueException(Exception):
    """Exception to handle continue statements"""
    pass


class BlazeFuture:
    """The Promise/Future-like runtime value returned by calling an
    'async Function'.

    BlazeLang has no real event loop or scheduler, so async functions run
    eagerly (synchronously, to completion) the moment they're called --
    exactly like a normal function -- except their outcome (result or
    raised error) is captured here instead of being returned/raised
    directly. 'await' is what actually surfaces that outcome: unwrapping
    the value on success, or re-raising the original error on failure.
    This keeps 'async'/'await' fully deterministic and composable with the
    rest of the tree-walking interpreter (recursion, arguments, etc.) with
    no additional runtime machinery.
    """

    def __init__(self, value: Any = None, error: BaseException = None):
        self.value = value
        self.error = error

    @property
    def is_rejected(self) -> bool:
        return self.error is not None

    def __str__(self):
        return "<Future rejected>" if self.is_rejected else f"<Future {self._preview()}>"

    def _preview(self):
        return self.value

    def __repr__(self):
        return self.__str__()


class AttributeHolder:
    """Shared, beginner-friendly API for inspecting custom attributes
    (`@name` / `@name(args)`) attached to a Function or Class.

    Attributes are pure metadata: attaching one never runs any code by
    itself. `self.attributes` maps attribute name -> list of already
    evaluated argument values (empty list for a bare '@name').
    """

    def hasAttribute(self, name: str) -> bool:
        return name in self.attributes

    def getAttribute(self, name: str):
        if name not in self.attributes:
            return None
        args = self.attributes[name]
        if not args:
            return True       # bare attribute, e.g. @logged
        if len(args) == 1:
            return args[0]    # single-argument attribute, e.g. @role("admin")
        return list(args)     # multi-argument attribute

    def getAttributes(self) -> list:
        return list(self.attributes.keys())


class Function(AttributeHolder):
    """Represents a BlazeLang function"""
    def __init__(self, name: str, parameters: List[str], body: BlockStatement,
                 is_meta: bool = False, closure: Dict = None,
                 owner_class=None, access_modifier: str = 'public',
                 attributes: Dict[str, list] = None, is_async: bool = False):
        self.name = name
        self.parameters = parameters
        self.body = body
        self.is_meta = is_meta
        # Async functions still execute eagerly (see BlazeFuture) -- this
        # flag only changes what __call__ hands back: a BlazeFuture wrapping
        # the outcome instead of the outcome itself.
        self.is_async = is_async
        self.closure = closure or {}
        self.is_method = False
        self.owner_class = owner_class          # Class this method belongs to (or None for free functions)
        # name -> list of evaluated argument values; see AttributeHolder.
        self.attributes = attributes or {}
        # Meta functions (constructors) are always public. Private and static
        # modifiers only ever apply to regular methods -- a constructor must be
        # reachable from anywhere a class can be instantiated, so we normalize
        # access_modifier here regardless of what the caller passed in. This is
        # defense-in-depth: visit_ClassDeclaration also normalizes this before
        # constructing meta Function objects, but enforcing it here as well
        # means any other code path that builds a meta Function directly (e.g.
        # ConstructorDeclaration handling) can't accidentally end up private.
        self.access_modifier = 'public' if is_meta else access_modifier  # 'public' or 'private'

    def __call__(self, interpreter, arguments: List[Any], instance_scope: Dict = None) -> Any:
        """Execute the function"""
        previous_scope = interpreter.current_scope
        previous_class = interpreter.current_class

        # New scope inherits from closure
        new_scope = dict(self.closure)

        # If instance_scope is provided (for methods), merge it
        if instance_scope:
            new_scope.update(instance_scope)

        interpreter.current_scope = new_scope
        # While this method body runs, the interpreter is "inside" its owner class,
        # which is what lets private members be called from other methods of the
        # same class (e.g. this.InternalInfo()) while still blocking outside access.
        # This applies identically whether the function is a regular method or a
        # meta function (constructor) -- both run through this same __call__, so
        # current_class is set the same way for either, and private/static access
        # checks behave consistently in both cases.
        interpreter.current_class = self.owner_class

        # Bind parameters
        for i, param in enumerate(self.parameters):
            if i < len(arguments):
                new_scope[param] = {
                    'value': arguments[i],
                    'constant': False
                }
            else:
                new_scope[param] = {
                    'value': None,
                    'constant': False
                }

        # Lifecycle hooks apply to normal instance methods only.  Meta hooks
        # themselves and legacy Meta methods never re-enter this path.
        hooks = None
        if self.is_method and not self.is_meta and self.owner_class:
            hooks = self.owner_class.meta_hooks

        def run_hook(hook_name, hook_arguments):
            hook = hooks.get(hook_name) if hooks else None
            if hook:
                return hook(interpreter, hook_arguments, instance_scope)

        # A string that also carries this method's custom attributes, so a
        # Meta hook can do `method.hasAttribute("role")` while everything
        # that just treats it as the method's name keeps working.
        method_token = MethodName(self.name, self.attributes) if hooks else self.name

        interpreter.call_stack.append(f"{self.name}()")
        try:
            if hooks:
                run_hook('OnCall', [method_token, arguments])
                run_hook('Before', [method_token, arguments])
            returned_explicitly = False
            try:
                result = interpreter.visit(self.body)
            except ReturnException as ret:
                result = ret.value
                returned_explicitly = True
            except Exception as error:
                if hooks:
                    run_hook('OnError', [method_token, str(error)])
                # An async function's body failing doesn't raise out of the
                # call itself -- like a rejected Promise, the error is
                # captured on the Future and only surfaces when something
                # 'await's it (see visit_AwaitExpression).
                if self.is_async:
                    return BlazeFuture(error=error)
                raise
            if hooks:
                run_hook('OnReturn', [method_token, result])
                run_hook('After', [method_token, result])
            # Legacy Meta functions are statement-like unless they explicitly
            # return a value (HTTP handlers rely on that established form).
            if self.is_meta and not returned_explicitly:
                return None
            if self.is_async:
                return BlazeFuture(value=result)
            return result
        finally:
            interpreter.call_stack.pop()
            interpreter.current_scope = previous_scope
            interpreter.current_class = previous_class

    def __str__(self):
        return f"<function {self.name}>"

    def __repr__(self):
        return self.__str__()


class MethodName(str):
    """The method-name value passed as the first argument to Meta lifecycle
    hooks (OnCall, Before, OnReturn, After, OnError). Behaves exactly like
    the plain string it always was -- so existing hook bodies that compare
    it, concatenate it, or Show() it keep working unchanged -- but also
    carries the method's custom attributes so a hook can inspect them via
    `method.hasAttribute(...)`, `method.getAttribute(...)`, and
    `method.getAttributes()`.
    """
    def __new__(cls, name: str, attributes: Dict[str, list]):
        instance = str.__new__(cls, name)
        instance.attributes = attributes or {}
        return instance

    def hasAttribute(self, name: str) -> bool:
        return name in self.attributes

    def getAttribute(self, name: str):
        if name not in self.attributes:
            return None
        args = self.attributes[name]
        if not args:
            return True
        if len(args) == 1:
            return args[0]
        return list(args)

    def getAttributes(self) -> list:
        return list(self.attributes.keys())


class Class(AttributeHolder):
    """Represents a BlazeLang class"""
    def __init__(self, name: str, parent_class=None, attributes: Dict[str, list] = None):
        self.name = name
        self.parent_class = parent_class
        self.methods = {}
        self.static_members = {}
        # Hook name -> Function.  Each hook receives method name first, then
        # arguments/result/error as appropriate.
        self.meta_hooks = {}
        # name -> list of evaluated argument values; see AttributeHolder.
        self.attributes = attributes or {}
        # Declared `var`/`constant` fields at the class level: name -> dict with
        # 'default' (the unevaluated default-value AST node), 'visibility'
        # ('public'/'private'/'protected'/'default'), 'is_constant', and
        # 'is_static'. Field visibility mirrors how method access_modifier
        # works, but is tracked separately since fields live in
        # Instance.properties, not Class.methods.
        self.fields = {}

    def instantiate(self, interpreter, arguments: List[Any]) -> 'Instance':
        """Create a new instance of this class"""
        instance = Instance(self)

        # Initialize declared fields (including inherited ones) with their
        # default values before the constructor runs, so the constructor can
        # see and override them via 'this'.
        for cls in self._mro():
            for field_name, decl in cls.fields.items():
                if decl['is_static']:
                    continue
                default_value = interpreter.visit(decl['default']) if decl['default'] is not None else None
                instance.properties[field_name] = default_value
                instance.field_visibility[field_name] = decl['visibility']
                instance.field_owner[field_name] = cls

        if 'constructor' in self.methods:
            constructor = self.methods['constructor']
            # Create instance scope with 'this' bound to the instance
            instance_scope = {'this': {'value': instance, 'constant': True}}
            # Pass instance_scope to the constructor
            constructor(interpreter, arguments, instance_scope)

        return instance

    def _mro(self):
        """Root-first chain of this class and its ancestors, so subclass field
        declarations correctly override same-named parent fields."""
        chain = []
        cls = self
        while cls:
            chain.append(cls)
            cls = cls.parent_class
        return list(reversed(chain))

    def __str__(self):
        return f"<class {self.name}>"

    def __repr__(self):
        return self.__str__()


class Instance:
    """Represents an instance of a BlazeLang class"""
    def __init__(self, cls: Class):
        self.cls = cls
        self.properties = {}
        # Per-field visibility/owner, populated from the class's declared
        # fields at instantiation time. Properties set dynamically at runtime
        # (not declared with 'var'/'constant' in the class body) have no
        # entry here and are treated as public, matching existing behavior.
        self.field_visibility = {}
        self.field_owner = {}

    def get(self, name: str) -> Any:
        if name in self.properties:
            return self.properties[name]
        if name in self.cls.methods:
            return self.cls.methods[name]
        # Static members (public or private) are also reachable from inside the
        # class via `this.StaticFn()` or `this.StaticValue` -- including from the
        # constructor. Meta functions (constructors) are invoked through the same
        # Function.__call__ path as regular methods, so current_class is set
        # correctly for them too, and _check_member_access still enforces
        # `private` the normal way. Without this lookup, a constructor or method
        # trying to reach a static sibling via `this` would silently get None.
        if name in self.cls.static_members:
            return self.cls.static_members[name]
        if self.cls.parent_class:
            if name in self.cls.parent_class.methods:
                return self.cls.parent_class.methods.get(name)
            if name in self.cls.parent_class.static_members:
                return self.cls.parent_class.static_members.get(name)
        return None

    def set(self, name: str, value: Any):
        self.properties[name] = value

    def __str__(self):
        return f"<{self.cls.name} instance>"

    def __repr__(self):
        return self.__str__()


class StaticField:
    """Holds a static `var`/`constant` class field's value, name, owner class,
    and visibility -- kept distinct from Function so static field reads/writes
    (ClassName.Field, this.Field) never get confused with static method calls,
    while still exposing the same access_modifier/owner_class shape that
    _check_member_access expects."""
    def __init__(self, name: str, value: Any, owner_class: 'Class',
                 is_constant: bool = False, visibility: str = 'public'):
        self.name = name
        self.value = value
        self.owner_class = owner_class
        self.is_constant = is_constant
        self.access_modifier = visibility

    def __str__(self):
        return self._format_for_display()

    def _format_for_display(self):
        return str(self.value)

    def __repr__(self):
        return self.__str__()


class BoundMethod:
    """Wraps a method with its instance for 'this' binding"""
    def __init__(self, func: Function, instance: Instance):
        self.func = func
        self.instance = instance
        self.func.is_method = True

    def __call__(self, interpreter, arguments: List[Any]) -> Any:
        """Execute the method with 'this' bound to the instance"""
        instance_scope = {'this': {'value': self.instance, 'constant': True}}
        return self.func(interpreter, arguments, instance_scope)

    # Delegate custom-attribute inspection to the underlying Function so
    # `instance.SomeMethod.hasAttribute(...)` works the same as it does on
    # an unbound Function/Meta.
    def hasAttribute(self, name: str) -> bool:
        return self.func.hasAttribute(name)

    def getAttribute(self, name: str):
        return self.func.getAttribute(name)

    def getAttributes(self) -> list:
        return self.func.getAttributes()

    def __str__(self):
        return f"<method {self.func.name}>"

    def __repr__(self):
        return self.__str__()


class SuperProxy:
    """The parent-class view of an instance used by ``super.Method()``."""
    def __init__(self, parent_class: Class, instance: Instance):
        self.parent_class = parent_class
        self.instance = instance


def _struct_display_value(value: Any) -> str:
    """Format a value for Struct Show()/string representation. Mirrors
    Interpreter._format_value's primitive formatting so nested values inside
    a Struct (numbers, strings, booleans, null, arrays, objects) read the
    same way they would anywhere else in BlazeLang, without requiring an
    Interpreter instance (Struct's __str__ has no interpreter reference)."""
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
    if isinstance(value, list):
        return '[' + ', '.join(_struct_display_value(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(f"'{k}': {_struct_display_value(v)}" for k, v in value.items()) + '}'
    return str(value)


class StructType:
    """Represents a BlazeLang Struct type -- a lightweight, data-only type
    independent of the Class system. A Struct has no methods, constructors,
    or inheritance; construction itself initializes fields either
    positionally, by name, or with declared defaults."""

    def __init__(self, name: str, fields: List[str], defaults: Dict[str, Any]):
        self.name = name
        self.fields = fields                # field names, in declaration order
        self.defaults = defaults            # field name -> unevaluated default AST node (or None)

    def instantiate(self, interpreter, positional_args: List[Any], named_args: List[tuple],
                     line=None, column=None, filename=None) -> 'StructInstance':
        """Build a new instance from positional and/or named arguments.

        `named_args` is a list of (name, value) pairs rather than a dict so
        that a field named more than once by name (e.g.
        `User(name: "A", name: "B")`) is still caught as a duplicate, not
        silently collapsed by the last value winning.
        """
        if len(positional_args) > len(self.fields):
            raise StructConstructionError(
                f"Struct '{self.name}' takes at most {len(self.fields)} positional "
                f"argument(s), but received {len(positional_args)}",
                line, column, filename,
            )

        values: Dict[str, Any] = {}
        assigned_by: Dict[str, str] = {}

        for index, value in enumerate(positional_args):
            field_name = self.fields[index]
            values[field_name] = value
            assigned_by[field_name] = 'positional'

        for field_name, value in named_args:
            if field_name not in self.fields:
                raise UnknownStructFieldError(self.name, field_name, line, column, filename)
            if field_name in assigned_by:
                raise DuplicateStructArgumentError(self.name, field_name, line, column, filename)
            values[field_name] = value
            assigned_by[field_name] = 'named'

        instance = StructInstance(self)
        for field_name in self.fields:
            if field_name in values:
                instance.properties[field_name] = values[field_name]
            else:
                default_node = self.defaults.get(field_name)
                instance.properties[field_name] = (
                    interpreter.visit(default_node) if default_node is not None else None
                )
        return instance

    def __str__(self):
        return f"<struct {self.name}>"

    def __repr__(self):
        return self.__str__()


class StructInstance:
    """Represents an instance of a BlazeLang Struct.

    Deliberately its own runtime type (not a plain dict) so BlazeLang's
    `type()` and equality/identity behavior can distinguish a Struct
    instance from an ordinary object/dictionary, while still storing fields
    in a plain `properties` dict -- mirroring `Instance` -- so field
    access/assignment and any duck-typed integration (e.g. JSON
    serialization) can reuse the same shape.
    """

    def __init__(self, struct_type: StructType):
        self.struct_type = struct_type
        self.properties: Dict[str, Any] = {}

    def get(self, name: str) -> Any:
        return self.properties.get(name)

    def set(self, name: str, value: Any):
        self.properties[name] = value

    def __str__(self):
        return self._format_for_display()

    def _format_for_display(self):
        field_lines = [
            f"  {field_name}: {_struct_display_value(self.properties.get(field_name))}"
            for field_name in self.struct_type.fields
        ]
        body = ",\n".join(field_lines)
        if body:
            return f"{self.struct_type.name} {{\n{body}\n}}"
        return f"{self.struct_type.name} {{}}"

    def __repr__(self):
        return self.__str__()


class EnumType:
    """Represents a BlazeLang Enum type -- a named, closed set of immutable
    members. Independent of the Class/Struct systems: no methods, fields,
    constructors, or inheritance. Members are stored in declaration order
    so iteration/inspection (and error messages) reflect source order."""

    def __init__(self, name: str):
        self.name = name
        self.members: Dict[str, 'EnumValue'] = {}
        self.members_in_order: List['EnumValue'] = []

    def values(self) -> List['EnumValue']:
        """Return all members, in declaration order -- backs Enum.values()."""
        return list(self.members_in_order)

    def from_value(self, value, line=None, column=None, filename=None) -> 'EnumValue':
        """Return the member whose resolved value equals `value` -- backs
        Enum.fromValue(value). Matching is exact on both type and value
        (an Integer value never matches a String-valued member and vice
        versa, and a Boolean is never treated as an Integer 0/1 match)."""
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise EnumValueNotFoundError(self.name, value, line, column, filename)
        for member in self.members_in_order:
            if type(member.value) is type(value) and member.value == value:
                return member
        raise EnumValueNotFoundError(self.name, value, line, column, filename)

    def __str__(self):
        return f"<enum {self.name}>"

    def __repr__(self):
        return self.__str__()


class EnumValue:
    """A single immutable member of a BlazeLang Enum (e.g. Status.Pending).
    Kept as its own runtime type (not a plain int/string) so that two
    different Enums with equal underlying values never compare equal to
    each other -- equality/hash are based on (enum type identity, member
    name), not on the underlying value alone."""

    def __init__(self, enum_type: EnumType, name: str, value):
        self.enum_type = enum_type
        self.name = name
        self.value = value

    def __eq__(self, other):
        if isinstance(other, EnumValue):
            return self.enum_type is other.enum_type and self.name == other.name
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash((id(self.enum_type), self.name))

    def __str__(self):
        return f"{self.enum_type.name}.{self.name}"

    def __repr__(self):
        return self.__str__()


class LastUpdate:
    """The `time`/`caller` snapshot of a Bind's most recent actual update.
    A plain attribute-holding object, deliberately -- BindValue.lastUpdate
    is read through the interpreter's normal PropertyAccess fallback
    (`hasattr`/`getattr`), the same path any other runtime object with
    public attributes already goes through, so no new property-access
    syntax or mechanism is needed for `score.lastUpdate.time`."""
    __slots__ = ('time', 'caller')

    def __init__(self, time: str, caller: str):
        self.time = time
        self.caller = caller

    def __str__(self):
        return f"{{time: {self.time}, caller: {self.caller}}}"

    def __repr__(self):
        return self.__str__()


class BindValue:
    """Runtime representation of a `bind` value -- a first-class BlazeLang
    type distinct from a plain variable. A BindValue wraps an underlying
    value of any existing BlazeLang type (int, string, bool, float, list,
    object, ...) and, alongside it, maintains its own state: the previous
    value, the original (origin) value, the full change history, a change
    counter, a simple lifecycle state, and metadata about its most recent
    actual update (when, and which function performed it).

    Only Bind values carry this metadata -- normal `var`/`constant`
    declarations continue to use the existing lightweight
    {'value', 'constant'} scope entry untouched, so this adds no overhead
    to ordinary variables.
    """

    # The set of metadata property names that only exist on a bind. Used
    # by visit_PropertyAccess to give a Bind-specific error (rather than a
    # generic "unknown property") when one of these is accessed on
    # something that isn't a BindValue.
    METADATA_PROPERTIES = frozenset({
        'value', 'previous', 'origin', 'history', 'changes', 'state', 'lastUpdate',
    })

    def __init__(self, initial_value: Any):
        self.value = initial_value
        self.previous = initial_value
        self.origin = initial_value
        self.history = [initial_value]
        self.changes = 0
        self.state = 'initial'
        self.lastUpdate = None

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """Same-value detection for Bind updates, reusing BlazeLang's
        existing value semantics (Python equality for its primitive/list/
        dict representations) -- with bool/int/float kept distinct from
        each other, matching how builtin_type already tells them apart."""
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        try:
            return a == b
        except Exception:
            return a is b

    def update(self, new_value: Any, caller: str) -> None:
        """Apply an assignment to this Bind. A no-op (aside from leaving
        `value` as-is) when the new value doesn't actually differ from the
        current one -- previous/origin/history/changes/state/lastUpdate are
        all left untouched for a same-value assignment."""
        if not self.history:
            # Should be unreachable -- __init__ always seeds history with
            # the origin value. Fail loudly with a BlazeLang error rather
            # than silently producing an inconsistent history.
            raise InvalidBindStateError("history is empty; a bind must always have at least its origin value")
        if self._values_equal(self.value, new_value):
            return
        self.previous = self.value
        self.value = new_value
        self.history.append(new_value)
        self.changes += 1
        self.state = 'changed'
        self.lastUpdate = LastUpdate(datetime.now().strftime('%H:%M'), caller)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"<bind value={self.value!r} state={self.state}>"


_VISITOR_MAP = {}


def _get_visitor(node_class):
    method_name = f'visit_{node_class.__name__}'
    func = getattr(Interpreter, method_name, Interpreter.generic_visit)
    _VISITOR_MAP[node_class] = func
    return func


class Interpreter:
    """Tree-walking interpreter for BlazeLang"""

    # Maximum nesting depth for eval()/evalFile() calling eval()/evalFile()
    # again (directly or indirectly), guarding against infinite/runaway
    # evaluation from a string that keeps re-evaluating itself.
    MAX_EVAL_DEPTH = 50

    def __init__(self, module_registry=None, loading_modules=None, filename=None, cli_args=None, package_document=None):
        self.global_scope = {}
        self.current_scope = self.global_scope
        # Tracks which Class's method body is currently executing (None at top level
        # or inside a free function). Used to enforce `private` access control.
        self.current_class = None
        self.filename = os.path.abspath(filename) if (filename and not filename.startswith("package:")) else filename
        self.module_registry = module_registry if module_registry is not None else {}
        self.loading_modules = loading_modules if loading_modules is not None else []
        self.current_exports = None
        self.call_stack = ["main()"]
        self.cli_args = list(cli_args or [])
        self.package_document = package_document
        self._eval_depth = 0
        self._visitor_cache = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register all built-in functions in global scope"""
        builtins = {
            'Show': self.builtin_Show,
            'Print': self.builtin_Print,
            'Input': self.builtin_Input,
            'len': self.builtin_len,
            'range': self.builtin_range,
            'type': self.builtin_type,
            'Upper': self.builtin_Upper,
            'Lower': self.builtin_Lower,
            'Trim': self.builtin_Trim,
            'Split': self.builtin_Split,
            'Join': self.builtin_Join,
            'Replace': self.builtin_Replace,
            'Contains': self.builtin_Contains,
            'StartsWith': self.builtin_StartsWith,
            'EndsWith': self.builtin_EndsWith,
            'Find': self.builtin_Find,
            'Reverse': self.builtin_Reverse,
            'Random': self.builtin_Random,
            'Sleep': self.builtin_Sleep,
            'Exit': self.builtin_Exit,
            'Int': self.builtin_Int,
            'Float': self.builtin_Float,
            'String': self.builtin_String,
            'Bool': self.builtin_Bool,
            'eval': self.builtin_eval,
            'evalFile': self.builtin_evalFile,
        }

        for name, func in builtins.items():
            self.global_scope[name] = {
                'value': func,
                'constant': True
            }

        # Save/Load/Delete/Exists/Clear/List.LocalStorage -- registered as
        # namespace objects (rather than flat functions) so BlazeLang source
        # can call e.g. `Save.LocalStorage("ai.epoch", 25)`. visit_PropertyAccess
        # already falls back to plain `getattr` for any object it doesn't
        # otherwise recognize, so no interpreter/parser changes beyond this
        # registration are needed for the dotted call syntax to work.
        for name, namespace in build_localstorage_namespaces().items():
            self.global_scope[name] = {
                'value': namespace,
                'constant': True
            }

    def interpret(self, node: ASTNode) -> Any:
        return self.visit(node)

    def visit(self, node: ASTNode) -> Any:
        if node is None:
            return None

        node_class = node.__class__
        try:
            visitor = _VISITOR_MAP[node_class]
        except KeyError:
            visitor = _get_visitor(node_class)

        try:
            return visitor(self, node)
        except BlazeError as error:
            error.attach_context(getattr(node, 'line', None), getattr(node, 'column', None),
                                 getattr(node, 'filename', None) or self.filename, self.call_stack)
            raise

    def generic_visit(self, node: ASTNode):
        raise NotImplementedError(f"No visit method for {type(node).__name__}")

    # =====================
    # Statement Visitors
    # =====================

    def visit_Program(self, node: Program) -> Any:
        result = None
        for statement in node.statements:
            try:
                result = self.visit(statement)
            except BreakException:
                raise LoopControlError("break")
            except ContinueException:
                raise LoopControlError("continue")
        return result

    def visit_VariableDeclaration(self, node: VariableDeclaration) -> Any:
        value = self.visit(node.value) if node.value is not None else None

        self.current_scope[node.name] = {
            'value': value,
            'constant': node.is_constant,
            # Visibility is recorded for parity with class fields, but is not
            # enforced for local/global variables -- 'public var' and
            # 'private var' at this level behave identically to plain 'var'.
            'visibility': node.visibility,
        }

        return value

    def visit_BindDeclaration(self, node: BindDeclaration) -> Any:
        """Create a new Bind. Isolated from visit_VariableDeclaration on
        purpose -- a Bind's initial creation always seeds `origin`/`history`
        from scratch and starts in the 'initial' state, which is
        meaningfully different from a plain var's scope entry."""
        if not node.name:
            raise InvalidBindDeclarationError(
                "a bind needs a name", getattr(node, 'line', None), getattr(node, 'column', None), self.filename
            )
        value = self.visit(node.value) if node.value is not None else None
        bind_value = BindValue(value)

        self.current_scope[node.name] = {
            'value': bind_value,
            'constant': False,
        }

        return bind_value

    def _current_caller_name(self) -> str:
        """The BlazeLang function currently performing an update, derived
        from the existing call_stack (see Function.__call__, which pushes
        "name()" on entry and pops it on exit) -- never a Python function
        name. Top-level code with no enclosing BlazeLang function call
        reports as '<global>' rather than crashing or leaking the
        interpreter's internal "main()" sentinel."""
        if len(self.call_stack) <= 1:
            return "<global>"
        top = self.call_stack[-1]
        return top[:-2] if top.endswith("()") else top

    def visit_ExpressionStatement(self, node: ExpressionStatement) -> Any:
        return self.visit(node.expression)

    def visit_BlockStatement(self, node: BlockStatement) -> Any:
        result = None
        for statement in node.statements:
            try:
                result = self.visit(statement)
            except ReturnException as ret:
                raise ret
        return result

    def visit_IfStatement(self, node: IfStatement) -> Any:
        condition = self.visit(node.condition)

        if self.is_truthy(condition):
            return self.visit(node.then_branch)

        for elif_condition, elif_body in node.else_if_branches:
            if self.is_truthy(self.visit(elif_condition)):
                return self.visit(elif_body)

        if node.else_branch:
            return self.visit(node.else_branch)

        return None

    def visit_WhileStatement(self, node: WhileStatement) -> Any:
        result = None
        cond = node.condition
        body = node.body
        body_stmts = body.statements
        if len(body_stmts) == 1:
            target_node = body_stmts[0]
            if isinstance(target_node, ExpressionStatement):
                target_node = target_node.expression
            while bool(self.visit(cond)):
                try:
                    result = self.visit(target_node)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        while bool(self.visit(cond)):
            try:
                result = self.visit(body)
            except BreakException:
                break
            except ContinueException:
                continue
        return result

    def visit_ForStatement(self, node: ForStatement) -> Any:
        iterable = self.visit(node.iterable)

        # A very common numeric reduction has no observable per-iteration
        # side effects except updating its accumulator.  Execute it directly
        # instead of allocating a loop variable entry and dispatching three
        # AST visitors per item.  The structural guard deliberately keeps all
        # non-trivial loops (including break/continue and function calls) on
        # the established general path.
        fast_result = self._try_fast_numeric_accumulation(node, iterable)
        if fast_result is not _NO_FAST_PATH:
            return fast_result

        if isinstance(iterable, (list, range, str)):
            result = None
            cur_scope = self.current_scope
            var_name = node.variable
            entry = cur_scope.get(var_name)
            if entry is None or not isinstance(entry, dict) or entry.get('constant') or isinstance(entry.get('value'), BindValue):
                entry = {'value': None, 'constant': False}
                cur_scope[var_name] = entry

            body = node.body
            body_stmts = body.statements
            if len(body_stmts) == 1:
                target_node = body_stmts[0]
                if isinstance(target_node, ExpressionStatement):
                    target_node = target_node.expression
                for item in iterable:
                    entry['value'] = item
                    try:
                        result = self.visit(target_node)
                    except BreakException:
                        break
                    except ContinueException:
                        continue
                return result

            for item in iterable:
                entry['value'] = item
                try:
                    result = self.visit(body)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        raise BlazeRuntimeError(f"Cannot iterate over {type(iterable).__name__}")

    def _try_fast_numeric_accumulation(self, node, iterable):
        """Run ``for i in range(...){ total += i }`` at Python speed.

        This is intentionally narrow: it only accepts a one-statement body
        whose right hand side is precisely the loop variable.  That makes the
        optimization semantics-preserving even in the presence of mutable
        scopes and user-defined functions.
        """
        if not isinstance(iterable, range) or len(node.body.statements) != 1:
            return _NO_FAST_PATH
        statement = node.body.statements[0]
        # Older parser paths expose assignment expressions directly, while
        # newer ones wrap ordinary expressions in ExpressionStatement.
        assignment = statement.expression if isinstance(statement, ExpressionStatement) else statement
        if (not isinstance(assignment, Assignment) or assignment.operator not in ('+=', '-=')
                or not isinstance(assignment.value, Identifier)
                or assignment.value.name != node.variable):
            return _NO_FAST_PATH
        scope = self.current_scope if assignment.name in self.current_scope else self.global_scope
        entry = scope.get(assignment.name)
        if entry is None or entry.get('constant') or isinstance(entry.get('value'), BindValue):
            return _NO_FAST_PATH
        current = entry['value']
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            return _NO_FAST_PATH
        # Python's C-level sum consumes range lazily and performs the same
        # integer arithmetic BlazeLang exposes for this restricted form.
        delta = sum(iterable)
        entry['value'] = current + delta if assignment.operator == '+=' else current - delta
        return entry['value']

    def visit_ForEachStatement(self, node: ForEachStatement) -> Any:
        return self.visit_ForStatement(node)

    def visit_BreakStatement(self, node: BreakStatement) -> None:
        raise BreakException()

    def visit_ContinueStatement(self, node: ContinueStatement) -> None:
        raise ContinueException()

    def visit_ReturnStatement(self, node: ReturnStatement) -> Any:
        value = self.visit(node.value) if node.value else None
        raise ReturnException(value)

    def visit_ThrowStatement(self, node: ThrowStatement) -> Any:
        value = self.visit(node.value)
        error_msg = str(value)

        # Add line number context if available
        if hasattr(node, 'line') and node.line:
            error_msg = f"{error_msg} (at line {node.line})"

        raise BlazeRuntimeError(error_msg)

    def visit_TryCatchStatement(self, node: TryCatchStatement) -> Any:
        try:
            return self.visit(node.try_block)
        except BlazeRuntimeError as e:
            # This is a thrown error from the BlazeLang code
            # Catch it and execute the catch block
            previous_scope = self.current_scope
            catch_scope = dict(previous_scope)
            catch_scope[node.error_var] = {
                'value': str(e),
                'constant': False
            }
            self.current_scope = catch_scope
            try:
                result = self.visit(node.catch_block)
            finally:
                self.current_scope = previous_scope
            return result
        except ReturnException as e:
            raise e
        except Exception as e:
            # Catch any other Python exceptions
            previous_scope = self.current_scope
            catch_scope = dict(previous_scope)
            catch_scope[node.error_var] = {
                'value': str(e),
                'constant': False
            }
            self.current_scope = catch_scope
            try:
                result = self.visit(node.catch_block)
            finally:
                self.current_scope = previous_scope
            return result
        finally:
            if node.finally_block:
                self.visit(node.finally_block)

    def visit_AttributeDefinition(self, node: AttributeDefinition) -> None:
        """'Define @name(...)' only registers the attribute at parse time
        (Parser.defined_attributes) -- there is nothing to execute here."""
        return None

    def _eval_attributes(self, attribute_usages) -> Dict[str, list]:
        """Evaluate a list of AttributeUsage AST nodes into name -> [values].
        Runs once, at the point the decorated declaration executes -- the
        same as evaluating any other expression in that scope."""
        result = {}
        if attribute_usages:
            for usage in attribute_usages:
                result[usage.name] = [self.visit(arg) for arg in usage.arguments]
        return result

    def visit_FunctionDeclaration(self, node: FunctionDeclaration) -> None:
        func = Function(
            name=node.name,
            parameters=node.parameters,
            body=node.body,
            is_meta=node.is_meta,
            closure=dict(self.current_scope),
            attributes=self._eval_attributes(getattr(node, 'attributes', None)),
            is_async=getattr(node, 'is_async', False),
        )

        self.current_scope[node.name] = {
            'value': func,
            'constant': True
        }
        return None

    def visit_FunctionExpression(self, node: FunctionExpression) -> Function:
        """Create a closure for an anonymous function stored in an API object."""
        return Function(
            name='<anonymous>', parameters=node.parameters, body=node.body,
            closure=dict(self.current_scope),
        )

    def visit_ClassDeclaration(self, node: ClassDeclaration) -> None:
        parent_cls = None
        if node.parent_class:
            if node.parent_class in self.current_scope:
                parent_cls = self.current_scope[node.parent_class]['value']
            elif node.parent_class in self.global_scope:
                parent_cls = self.global_scope[node.parent_class]['value']

            # Struct is intentionally independent of the Class system and
            # supports no inheritance in either direction -- a Class cannot
            # extend a Struct, even though both are found through the same
            # scope lookup above.
            if isinstance(parent_cls, StructType):
                raise StructInheritanceError(
                    f"Class '{node.name}' cannot inherit from Struct '{node.parent_class}'",
                    getattr(node, 'line', None), getattr(node, 'column', None), self.filename,
                )

        cls = Class(
            name=node.name,
            parent_class=parent_cls,
            attributes=self._eval_attributes(getattr(node, 'attributes', None)),
        )

        for member in node.members:
            if isinstance(member, ConstructorDeclaration):
                func = Function(
                    name='constructor',
                    parameters=member.parameters,
                    body=member.body,
                    is_meta=True,
                    closure=dict(self.current_scope),
                    owner_class=cls
                )
                cls.methods['constructor'] = func
            elif isinstance(member, FunctionDeclaration):
                # Meta functions (constructors declared via the `meta` keyword on
                # a regular function-style member) must be written bare -- no
                # modifier at all, not even an explicit `public`. A constructor
                # has to be reachable wherever the class itself is reachable, so
                # writing any modifier in front of `Meta` is rejected outright
                # rather than silently accepted or discarded.
                is_meta = member.is_meta
                if is_meta and getattr(member, 'had_explicit_modifier', False):
                    bad_modifier = 'static' if member.is_static else member.access_modifier
                    raise InvalidConstructorModifierError(
                        bad_modifier,
                        class_name=cls.name,
                        line=getattr(member, 'line', None),
                        column=getattr(member, 'column', None),
                        filename=self.filename,
                    )

                func = Function(
                    name=member.name,
                    parameters=member.parameters,
                    body=member.body,
                    is_meta=is_meta,
                    closure=dict(self.current_scope),
                    owner_class=cls,
                    access_modifier=member.access_modifier,
                    attributes=self._eval_attributes(getattr(member, 'attributes', None)),
                )
                if member.is_static:
                    # Static members live in their own bucket so instances never
                    # see them via Instance.get(), and they're called as ClassName.Member(...)
                    # -- and, with the Instance.get() fallback above, also reachable
                    # from inside the class via this.Member(...), including from
                    # meta functions (constructors), same as any other method.
                    cls.static_members[member.name] = func
                else:
                    func.is_method = True
                    cls.methods[member.name] = func
            elif isinstance(member, MetaHookDeclaration):
                cls.meta_hooks[member.hook_name] = Function(
                    name=member.hook_name,
                    parameters=member.parameters,
                    body=member.body,
                    closure=dict(self.current_scope),
                    owner_class=cls,
                )
            elif isinstance(member, VariableDeclaration):
                # A `var`/`constant` field declared directly in the class body,
                # e.g. `public var name = "Rohit"` or `private var secret`.
                # Visibility of 'default' (no modifier written) behaves as
                # public, matching the language's default for unmarked class
                # members. Static var fields are evaluated once, immediately,
                # and stored on the class itself (ClassName.Field), separate
                # from per-instance fields which get their default
                # (re-)evaluated fresh for every new instance in
                # Class.instantiate.
                visibility = member.visibility if member.visibility != 'default' else 'public'
                if member.is_static:
                    value = self.visit(member.value) if member.value is not None else None
                    cls.static_members[member.name] = StaticField(
                        name=member.name,
                        value=value,
                        owner_class=cls,
                        is_constant=member.is_constant,
                        visibility=visibility,
                    )
                else:
                    cls.fields[member.name] = {
                        'default': member.value,
                        'visibility': visibility,
                        'is_constant': member.is_constant,
                        'is_static': False,
                    }

        self.current_scope[node.name] = {
            'value': cls,
            'constant': True
        }
        return None

    def visit_ConstructorDeclaration(self, node: ConstructorDeclaration) -> None:
        pass

    def visit_StructDeclaration(self, node: StructDeclaration) -> None:
        """Register a Struct type. Unlike Class, this only ever records field
        names (in order) and their unevaluated default-value expressions --
        Struct has no methods, static members, or constructor to process."""
        fields = [struct_field.name for struct_field in node.fields]
        defaults = {struct_field.name: struct_field.default_value for struct_field in node.fields}
        struct_type = StructType(name=node.name, fields=fields, defaults=defaults)

        self.current_scope[node.name] = {
            'value': struct_type,
            'constant': True
        }
        return None

    def visit_EnumDeclaration(self, node: EnumDeclaration) -> None:
        """Register an Enum type. Members are evaluated once, in
        declaration order: an explicit value is used as-is, and a member
        with no explicit value auto-increments from the previous *numeric*
        value (starting at 0), independent of any string-valued members
        that may appear alongside it. Duplicate member names are already
        rejected by the parser; duplicate resolved values are rejected
        here, since implicit auto-increment can only be resolved at this
        point."""
        enum_type = EnumType(node.name)
        seen_values = {}
        next_numeric = 0

        for member in node.members:
            if member.value is not None:
                value = self.visit(member.value)
                if isinstance(value, int):
                    next_numeric = value + 1
            else:
                value = next_numeric
                next_numeric += 1

            value_key = (type(value).__name__, value)
            if value_key in seen_values:
                raise DuplicateEnumValueError(
                    node.name, member.name, value,
                    member.line, member.column, member.filename,
                )
            seen_values[value_key] = member.name

            enum_value = EnumValue(enum_type, member.name, value)
            enum_type.members[member.name] = enum_value
            enum_type.members_in_order.append(enum_value)

        self.current_scope[node.name] = {
            'value': enum_type,
            'constant': True,
        }
        return None

    def _enum_values_call(self, enum_type: EnumType, args) -> List[EnumValue]:
        """Validates the argument count for Enum.values() before delegating
        to EnumType.values, for the same reason as _enum_from_value_call."""
        if args:
            raise ArgumentError(f"{enum_type.name}.values", 0, len(args))
        return enum_type.values()

    def _enum_from_value_call(self, enum_type: EnumType, args) -> EnumValue:
        """Validates the argument count for Enum.fromValue(value) before
        delegating to EnumType.from_value, so a wrong call arity produces a
        normal BlazeLang ArgumentError instead of a raw Python TypeError."""
        if len(args) != 1:
            raise ArgumentError(f"{enum_type.name}.fromValue", 1, len(args))
        return enum_type.from_value(args[0])

    def _list_append_call(self, items: list, method_name: str, args) -> None:
        """Shared implementation backing both list.append() and list.push():
        validates the argument count, then mutates `items` in place by
        adding the single given value to the end. Both method names funnel
        through here so they stay perfectly in sync. Returns None, matching
        BlazeLang's other in-place mutating calls (e.g. Reverse mutates and
        returns; here there's no useful return value, so None is used)."""
        if len(args) != 1:
            raise ArgumentError(f"list.{method_name}", 1, len(args))
        items.append(args[0])
        return None

    def _list_remove_call(self, items: list, args) -> None:
        """Implementation backing list.remove(value): validates the argument
        count, then mutates `items` in place by removing the first matching
        occurrence of the given value. Raises a BlazeLang ValueError (rather
        than a raw Python ValueError) if the value isn't present, mirroring
        how other builtins translate Python exceptions into BlazeLang ones."""
        if len(args) != 1:
            raise ArgumentError("list.remove", 1, len(args))
        value = args[0]
        try:
            items.remove(value)
        except PyValueError:
            raise BlazeValueError(f"Value {value!r} not found in list")
        return None

    def _list_contains_call(self, items: list, args) -> bool:
        """Implementation backing list.contains(value): validates the
        argument count, then reports whether the value occurs anywhere in
        the list. Read-only -- does not mutate `items`."""
        if len(args) != 1:
            raise ArgumentError("list.contains", 1, len(args))
        return args[0] in items

    def _list_insert_call(self, items: list, args) -> None:
        """Implementation backing list.insert(index, value): validates the
        argument count and that `index` is an integer (reusing the same
        integer-check rules as _resolve_index), then mutates `items` in
        place by inserting `value` at that position. Unlike normal element
        access/assignment, an out-of-range index is not an error here --
        Python's own list.insert clamps to the nearest valid position (e.g.
        an index past the end simply appends), and that clamping behavior
        is preserved rather than reproducing _resolve_index's strict range
        check, since "insert past the end" is a normal, useful thing to do."""
        if len(args) != 2:
            raise ArgumentError("list.insert", 2, len(args))
        index, value = args
        if isinstance(index, bool) or not isinstance(index, (int, float)):
            raise BlazeTypeError(
                f"List index must be an integer, got {type(index).__name__}"
            )
        if isinstance(index, float) and not index.is_integer():
            raise BlazeTypeError(
                f"List index must be an integer, got Float ({index})"
            )
        items.insert(int(index), value)
        return None

    # =====================
    # Expression Visitors
    # =====================

    def visit_NumberLiteral(self, node: NumberLiteral) -> float:
        return node.value

    def visit_StringLiteral(self, node: StringLiteral) -> str:
        return node.value

    def visit_BooleanLiteral(self, node: BooleanLiteral) -> bool:
        return node.value

    def visit_NullLiteral(self, node: NullLiteral) -> None:
        return None

    def visit_Identifier(self, node: Identifier) -> Any:
        name = node.name
        try:
            return self.current_scope[name]['value']
        except KeyError:
            if self.current_scope is not self.global_scope:
                try:
                    return self.global_scope[name]['value']
                except KeyError:
                    pass

            if name == "continue":
                raise ContinueException()
            if name == "break":
                raise BreakException()

            error = BlazeRuntimeError(f"Undefined variable '{name}'")
            known_names = list(self.current_scope) + list(self.global_scope)
            matches = get_close_matches(name, known_names, n=1, cutoff=0.6)
            if matches:
                error.hint = f"Did you mean '{matches[0]}'?"
            raise error

    def visit_Assignment(self, node: Assignment) -> Any:
        value = self.visit(node.value)
        name = node.name
        cur_scope = self.current_scope

        try:
            entry = cur_scope[name]
        except KeyError:
            if cur_scope is not self.global_scope:
                try:
                    entry = self.global_scope[name]
                except KeyError:
                    entry = {'value': None, 'constant': False}
                    cur_scope[name] = entry
            else:
                entry = {'value': None, 'constant': False}
                cur_scope[name] = entry

        if entry.get('constant'):
            raise ImmutableError(name)

        current = entry['value']

        if type(current) is BindValue:
            op = node.operator
            if op == '=':
                new_value = value
            elif op == '+=':
                new_value = current.value + value
            elif op == '-=':
                new_value = current.value - value
            elif op == '*=':
                new_value = current.value * value
            elif op == '/=':
                if value == 0:
                    raise BlazeZeroDivisionError()
                new_value = current.value / value
            else:
                raise InvalidBindAssignmentError(
                    name, op,
                    getattr(node, 'line', None), getattr(node, 'column', None), self.filename,
                )
            current.update(new_value, self._current_caller_name())
            return current.value

        op = node.operator
        if op == '=':
            entry['value'] = value
        elif op == '+=':
            entry['value'] += value
        elif op == '-=':
            entry['value'] -= value
        elif op == '*=':
            entry['value'] *= value
        elif op == '/=':
            entry['value'] /= value

        return entry['value']

    def visit_PropertyAssignment(self, node) -> Any:
        """Handle property assignment like this.name = value or obj.prop = value"""
        obj = self.visit(node.object)
        value = self.visit(node.value)

        if isinstance(obj, Instance):
            # Assigning to a declared private field from outside its owning
            # class is access too, not just reading -- reject it the same way.
            if node.property_name in obj.field_visibility:
                self._check_field_access(obj, node.property_name)

            field_decl = self._find_field_decl(obj.cls, node.property_name)
            if field_decl and field_decl.get('is_constant'):
                raise ImmutableError(node.property_name)

            if node.operator == '=':
                obj.set(node.property_name, value)
            elif node.operator == '+=':
                current = obj.get(node.property_name)
                if current is None:
                    current = '' if isinstance(value, str) else 0
                obj.set(node.property_name, current + value)
            elif node.operator == '-=':
                current = obj.get(node.property_name) or 0
                obj.set(node.property_name, current - value)
            elif node.operator == '*=':
                current = obj.get(node.property_name) or 1
                obj.set(node.property_name, current * value)
            elif node.operator == '/=':
                current = obj.get(node.property_name) or 1
                obj.set(node.property_name, current / value)
        elif isinstance(obj, StructInstance):
            # Struct fields are mutable by default and carry no visibility
            # modifiers or constant-ness -- BlazeLang has no established
            # immutable-field mechanism for Struct, so every field is a
            # plain read/write value.
            if node.operator == '=':
                obj.set(node.property_name, value)
            elif node.operator == '+=':
                current = obj.get(node.property_name)
                if current is None:
                    current = '' if isinstance(value, str) else 0
                obj.set(node.property_name, current + value)
            elif node.operator == '-=':
                current = obj.get(node.property_name) or 0
                obj.set(node.property_name, current - value)
            elif node.operator == '*=':
                current = obj.get(node.property_name) or 1
                obj.set(node.property_name, current * value)
            elif node.operator == '/=':
                current = obj.get(node.property_name) or 1
                obj.set(node.property_name, current / value)
        elif isinstance(obj, dict):
            if node.operator == '=':
                obj[node.property_name] = value
            elif node.operator == '+=':
                current = obj.get(node.property_name, '')
                obj[node.property_name] = current + value
            elif node.operator == '-=':
                current = obj.get(node.property_name, 0)
                obj[node.property_name] = current - value
            elif node.operator == '*=':
                current = obj.get(node.property_name, 1)
                obj[node.property_name] = current * value
            elif node.operator == '/=':
                current = obj.get(node.property_name, 1)
                obj[node.property_name] = current / value
        elif isinstance(obj, EnumType):
            # Enum members are immutable -- reject 'Status.Pending = ...'
            # the same way reassigning any other constant is rejected.
            raise ImmutableError(f"{obj.name}.{node.property_name}")
        elif isinstance(obj, EnumValue):
            # An Enum member's '.name'/'.value' are read-only, same as the
            # member itself.
            raise ImmutableError(f"{obj.enum_type.name}.{obj.name}.{node.property_name}")

        return value

    def _resolve_index(self, index: Any, size: int) -> int:
        """
        Convert an interpolated/evaluated index value into a valid Python
        list/string index, raising proper BlazeLang errors instead of
        letting raw Python ValueError/TypeError leak to the user (Bug 6).

        Negative indices are supported and count from the end (`items[-1]`
        is the last element) -- this matches the behavior already observed
        for plain list indexing before this fix (Python's native negative
        indexing was reachable for `int`-typed indices), so it is made
        explicit and applied consistently for both read and assignment,
        for both lists and strings (Bug 8). Out-of-range indices (positive
        or negative) raise the same BlazeIndexError used elsewhere, with a
        consistent message for both read and assignment (Bug 7).
        """
        if isinstance(index, bool) or not isinstance(index, (int, float)):
            raise BlazeTypeError(
                f"List index must be an integer, got {type(index).__name__}"
            )
        if isinstance(index, float) and not index.is_integer():
            raise BlazeTypeError(
                f"List index must be an integer, got Float ({index})"
            )
        idx = int(index)
        if idx < 0:
            idx += size
        if idx < 0 or idx >= size:
            raise BlazeIndexError(int(index), size)
        return idx

    def visit_ArrayElementAssignment(self, node) -> Any:
        """Handle array element assignment like arr[0] = value"""
        array = self.visit(node.array)
        index = self.visit(node.index)
        value = self.visit(node.value)

        if isinstance(array, list):
            idx = self._resolve_index(index, len(array))
            if node.operator == '=':
                array[idx] = value
            elif node.operator == '+=':
                array[idx] += value
            elif node.operator == '-=':
                array[idx] -= value
            elif node.operator == '*=':
                array[idx] *= value
            elif node.operator == '/=':
                array[idx] /= value
            return value

        # Bracket assignment into an object literal / map value, e.g.
        # project["api-key"] = "new-key". The key is whatever the index
        # expression evaluates to (normally a string) -- this mirrors
        # visit_PropertyAssignment's dict branch exactly, so
        # `obj["name"] = x` and `obj.name = x` behave identically.
        if isinstance(array, dict):
            if node.operator == '=':
                array[index] = value
            elif node.operator == '+=':
                current = array.get(index, '')
                array[index] = current + value
            elif node.operator == '-=':
                current = array.get(index, 0)
                array[index] = current - value
            elif node.operator == '*=':
                current = array.get(index, 1)
                array[index] = current * value
            elif node.operator == '/=':
                current = array.get(index, 1)
                array[index] = current / value
            return value

        if isinstance(array, Tensor):
            # Only supports assigning through a full index (t[i] = x for a
            # rank-1 Tensor, or after chaining sub-Tensor access); Tensor's
            # own __setitem__ validates index rank/bounds/dtype and raises
            # proper BlazeLang errors.
            try:
                if node.operator == '=':
                    array[index] = value
                else:
                    current = array[index]
                    op_fn = {
                        '+=': lambda a, b: a + b,
                        '-=': lambda a, b: a - b,
                        '*=': lambda a, b: a * b,
                        '/=': lambda a, b: a / b,
                    }[node.operator]
                    array[index] = op_fn(current, value)
            except BlazeError:
                raise
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot assign to Tensor index with {type(index).__name__}")
            return value

        raise BlazeRuntimeError(f"Cannot assign to index of {type(array).__name__}")

    def visit_BinaryOperation(self, node: BinaryOperation) -> Any:
        left = self.visit(node.left)

        op = node.operator
        if op in ('and', '&&'):
            if not bool(left):
                return left
            return self.visit(node.right)

        if op in ('or', '||'):
            if bool(left):
                return left
            return self.visit(node.right)

        right = self.visit(node.right)

        # Fast numeric path for primitive numbers (int / float)
        t_left, t_right = type(left), type(right)
        if (t_left is int or t_left is float) and (t_right is int or t_right is float):
            if op == '+':
                return left + right
            if op == '-':
                return left - right
            if op == '*':
                return left * right
            if op == '/':
                if right == 0:
                    raise BlazeZeroDivisionError()
                return left / right
            if op == '%':
                if right == 0:
                    raise BlazeZeroDivisionError()
                return left % right
            if op == '==':
                return left == right
            if op == '!=':
                return left != right
            if op == '>':
                return left > right
            if op == '<':
                return left < right
            if op == '>=':
                return left >= right
            if op == '<=':
                return left <= right
            if op in ('**', '^'):
                return left ** right

        if t_left is BindValue or t_right is BindValue:
            bind_name = node.left.name if t_left is BindValue and isinstance(node.left, Identifier) else (
                node.right.name if t_right is BindValue and isinstance(node.right, Identifier) else None
            )
            raise UnsupportedBindOperationError(op, bind_name)

        if op == '+':
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            try:
                return left + right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '+' to {type(left).__name__} and {type(right).__name__}")
        elif op == '-':
            try:
                return left - right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '-' to {type(left).__name__} and {type(right).__name__}")
        elif op == '*':
            try:
                return left * right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '*' to {type(left).__name__} and {type(right).__name__}")
        elif op == '/':
            if right == 0:
                raise BlazeZeroDivisionError()
            try:
                return left / right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '/' to {type(left).__name__} and {type(right).__name__}")
        elif op == '%':
            if right == 0:
                raise BlazeZeroDivisionError()
            try:
                return left % right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '%' to {type(left).__name__} and {type(right).__name__}")
        elif op in ('**', '^'):
            try:
                return left ** right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '{op}' to {type(left).__name__} and {type(right).__name__}")
        elif op == '==':
            return left == right
        elif op == '!=':
            return left != right
        elif op == '>':
            try:
                return left > right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '>' to {type(left).__name__} and {type(right).__name__}")
        elif op == '<':
            try:
                return left < right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '<' to {type(left).__name__} and {type(right).__name__}")
        elif op == '>=':
            try:
                return left >= right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '>=' to {type(left).__name__} and {type(right).__name__}")
        elif op == '<=':
            try:
                return left <= right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '<=' to {type(left).__name__} and {type(right).__name__}")

        raise BlazeRuntimeError(f"Unknown operator '{op}'")

    def visit_UnaryOperation(self, node: UnaryOperation) -> Any:
        operand = self.visit(node.operand)

        if node.operator == '-':
            if isinstance(operand, BindValue):
                bind_name = node.operand.name if isinstance(node.operand, Identifier) else None
                raise UnsupportedBindOperationError('-', bind_name)
            return -operand
        elif node.operator in ('not', '!'):
            return not self.is_truthy(operand)

        raise BlazeRuntimeError(f"Unknown unary operator '{node.operator}'")

    def visit_AwaitExpression(self, node) -> Any:
        """Resolve a BlazeFuture: return its value on success, or re-raise
        the original error it captured (a rejected Promise/Future). Awaiting
        anything else is a usage error -- 'await' only makes sense on the
        outcome of calling an 'async Function'."""
        value = self.visit(node.value)

        if isinstance(value, BlazeFuture):
            if value.is_rejected:
                raise value.error
            return value.value

        raise InvalidAwaitError(
            actual_type=self.builtin_type(value),
            line=getattr(node, 'line', None),
            column=getattr(node, 'column', None),
            filename=self.filename,
        )

    def visit_FunctionCall(self, node: FunctionCall) -> Any:
        callee = self.visit(node.callee)

        # Split call arguments into positional values and (name, value) pairs.
        # Kept as a list of pairs rather than a dict so a field named more
        # than once by name is still visible as a duplicate downstream,
        # instead of the last value silently winning.
        arguments = []
        named_arguments = []
        for arg_node in node.arguments:
            if isinstance(arg_node, NamedArgument):
                named_arguments.append((arg_node.name, self.visit(arg_node.value)))
            else:
                arguments.append(self.visit(arg_node))

        # Struct construction is the only place named arguments are actually
        # interpreted today -- it accepts any mix of positional and named
        # arguments and reports duplicates/unknown fields itself.
        if isinstance(callee, StructType):
            return callee.instantiate(
                self, arguments, named_arguments,
                getattr(node, 'line', None), getattr(node, 'column', None), self.filename,
            )

        if named_arguments:
            bad_name = named_arguments[0][0]
            raise BlazeTypeError(
                f"Named arguments are only supported when constructing a Struct "
                f"(got '{bad_name}:' on a call that isn't Struct construction)"
            )

        # Handle BoundMethod (instance methods)
        if isinstance(callee, BoundMethod):
            return callee(self, arguments)

        # Handle built-in Python callables.  Native extensions and Python
        # helpers must never leak raw host exceptions into BlazeLang output.
        if callable(callee) and not isinstance(callee, Function) and not isinstance(callee, Class):
            try:
                return callee(*arguments)
            except BlazeError:
                raise
            except Exception as error:
                operation = getattr(node.callee, 'property', None) or getattr(node.callee, 'name', None) or type(callee).__name__
                raise NativeModuleError(operation, error) from error

        # Handle BlazeLang functions
        if isinstance(callee, Function):
            return callee(self, arguments)

        # Handle class instantiation
        if isinstance(callee, Class):
            return callee.instantiate(self, arguments)

        callee_name = getattr(node.callee, 'name', None) or getattr(node.callee, 'property', None) or str(node.callee)
        raise NotCallableError(callee_name, actual_type=type(callee).__name__)

    def visit_ArrayLiteral(self, node: ArrayLiteral) -> list:
        return [self.visit(element) for element in node.elements]

    def visit_ObjectLiteral(self, node: ObjectLiteral) -> dict:
        result = {}
        for key, value_expr in node.properties.items():
            result[key] = self.visit(value_expr)
        return result

    # =====================
    # Reflect <operation>
    # =====================

    def visit_ReflectUserdata(self, node: ReflectUserdata) -> Any:
        """`Reflect <operation>(<source> { accept{} expect{} reject{} })`.

        `operation` is whatever identifier followed `Reflect` in source
        (`userdata`, `project`, `data`, `api`, ...) -- it is never matched
        against a fixed name, only carried along for diagnostics/context.

        Evaluates `source` (an HTTP response, parsed JSON, a File read, an
        object/Struct/class instance, or a list of any of those) and returns
        a *new* plain-object/array copy filtered by the field rules:

        - `expect` fields must exist on the value at that point in the tree,
          or a ReflectExpectedFieldError is raised.
        - `accept`, if given, whitelists which fields make it into the
          output at that level.
        - `reject` blacklists fields and always wins over `accept` -- a
          rejected field is never created/retained in the result.

        The rules recurse into nested objects and arrays of objects wherever
        a nested accept/expect/reject block is provided for that field.
        """
        source_value = self.visit(node.source)
        return self._reflect_filter(source_value, node.accept, node.expect, node.reject, node, "")

    @staticmethod
    def _reflect_object_view(value: Any):
        """Return (keys, getter) if `value` is an object-like runtime value
        Reflect knows how to walk (a plain dict -- which is what object
        literals, and any HTTP/JSON/File-sourced data, evaluate to -- a
        class Instance, or a Struct instance). Returns None for anything
        else (numbers, strings, booleans, etc.)."""
        if isinstance(value, dict):
            return list(value.keys()), value.__getitem__
        if isinstance(value, Instance):
            return list(value.properties.keys()), value.properties.__getitem__
        if isinstance(value, StructInstance):
            return list(value.properties.keys()), value.properties.__getitem__
        return None

    def _reflect_filter(self, value: Any, accept, expect, reject, node: 'ReflectUserdata', path: str) -> Any:
        """Recursively apply accept/expect/reject field specs to `value`."""

        # Arrays: apply the same specs element-wise (e.g. a list of user
        # objects from an HTTP/JSON array).
        if isinstance(value, list):
            return [
                self._reflect_filter(item, accept, expect, reject, node, path)
                for item in value
            ]

        if value is None:
            if expect and expect.fields:
                missing = next(iter(expect.fields))
                full_path = f"{path}.{missing}" if path else missing
                raise ReflectExpectedFieldError(full_path, node.operation, node.line, node.column, node.filename)
            return None

        view = self._reflect_object_view(value)
        if view is None:
            # A plain scalar reached a point in the tree where field rules
            # were declared -- there is nothing to accept/expect/reject.
            if accept or expect or reject:
                raise ReflectSourceTypeError(
                    type(value).__name__, path or None, node.operation, node.line, node.column, node.filename
                )
            return value

        keys, getter = view

        if expect:
            for field_name in expect.fields:
                if field_name not in keys:
                    full_path = f"{path}.{field_name}" if path else field_name
                    raise ReflectExpectedFieldError(full_path, node.operation, node.line, node.column, node.filename)

        selected_keys = [k for k in accept.fields if k in keys] if accept else list(keys)

        result = {}
        for key in selected_keys:
            sub_accept = accept.fields.get(key) if accept else None
            sub_expect = expect.fields.get(key) if expect else None
            sub_reject = reject.fields.get(key) if (reject and key in reject.fields) else None

            # 'reject' always overrides 'accept' -- a rejected field is never
            # created or retained in the resulting userdata. A *leaf* reject
            # entry (no nested block, e.g. `reject { password }`) drops the
            # field entirely; a reject entry with its own nested block
            # (e.g. `reject { address { secret_note } }`) only prunes the
            # named sub-fields, so the parent field itself is kept and
            # filtered recursively below.
            if reject and key in reject.fields and sub_reject is None:
                continue
            sub_path = f"{path}.{key}" if path else key
            field_value = getter(key)

            if sub_accept is not None or sub_expect is not None or sub_reject is not None:
                result[key] = self._reflect_filter(
                    field_value, sub_accept, sub_expect, sub_reject, node, sub_path
                )
            else:
                result[key] = field_value

        return result

    def _check_member_access(self, member: Any, member_name: str):
        """
        Enforce `private` visibility for methods and static fields/functions.
        A private member may only be invoked/read while the interpreter is
        currently executing inside that member's own class (e.g. called via
        `this` from another method of the same class, or from the constructor
        -- meta functions set current_class the same way as regular methods).
        Any outside access -- top-level code, another class, a free function
        -- is rejected. Works for both Function (methods, static functions)
        and StaticField (static var/constant fields), since both expose
        access_modifier/owner_class the same way.

        Note: meta functions (constructors) always have access_modifier
        normalized to 'public' at construction time, so this check is
        effectively a no-op for them -- they can never be rejected here.
        """
        if getattr(member, 'access_modifier', 'public') == 'private':
            if self.current_class is not member.owner_class:
                owner_name = member.owner_class.name if member.owner_class else None
                raise AccessError(member_name, class_name=owner_name)

    def _check_field_access(self, instance: 'Instance', field_name: str):
        """
        Enforce `private` visibility for instance `var`/`constant` fields
        declared in a class body (e.g. `private var password = "..."`).
        Only fields the class actually declared with 'var'/'constant' carry
        an entry in instance.field_visibility -- properties set dynamically
        at runtime with no declaration are treated as public, matching
        existing (pre-visibility-feature) behavior.
        """
        visibility = instance.field_visibility.get(field_name)
        if visibility == 'private':
            owner = instance.field_owner.get(field_name)
            if self.current_class is not owner:
                owner_name = owner.name if owner else None
                raise PrivateVariableAccessError(field_name, class_name=owner_name)

    def _find_field_decl(self, cls: 'Class', field_name: str):
        """Look up a field's declaration (default/visibility/is_constant/is_static)
        by walking from the given class up through its parent chain."""
        while cls:
            if field_name in cls.fields:
                return cls.fields[field_name]
            cls = cls.parent_class
        return None

    def visit_PropertyAccess(self, node: PropertyAccess) -> Any:
        obj = self.visit(node.object)

        if isinstance(obj, SuperProxy):
            method = obj.parent_class.methods.get(node.property)
            if method is None:
                raise PropertyError(node.property, f"parent class '{obj.parent_class.name}'")
            self._check_member_access(method, node.property)
            return BoundMethod(method, obj.instance)

        if isinstance(obj, dict):
            return obj.get(node.property)

        if isinstance(obj, StructInstance):
            return obj.properties.get(node.property)

        if isinstance(obj, Instance):
            # Declared instance fields (var/constant in the class body) are
            # visibility-checked before falling through to the general
            # get() lookup, so a private field can never leak out even
            # though its value also lives in obj.properties.
            if node.property in obj.properties and node.property in obj.field_visibility:
                self._check_field_access(obj, node.property)
                return obj.properties[node.property]

            result = obj.get(node.property)
            if result is not None:
                # If it's a method, return a bound method wrapper.
                # This also covers static members surfaced through
                # Instance.get()'s static_members fallback: a static function
                # accessed via `this.StaticFn` (including from inside a
                # constructor/meta function) still goes through the same
                # BoundMethod wrapping and _check_member_access enforcement
                # as any regular instance method.
                if isinstance(result, Function):
                    self._check_member_access(result, node.property)
                    return BoundMethod(result, obj)
                if isinstance(result, StaticField):
                    self._check_member_access(result, node.property)
                    return result.value
                return result
            return None

        if isinstance(obj, Class):
            # Custom-attribute inspection API (metadata only -- never
            # executes anything by itself). Checked before static members
            # so it can't be shadowed by a same-named field/method.
            if node.property in ('hasAttribute', 'getAttribute', 'getAttributes'):
                return getattr(obj, node.property)
            # Access static members first, then (legacy) instance methods
            # accessed directly off the class object.
            if node.property in obj.static_members:
                member = obj.static_members[node.property]
                self._check_member_access(member, node.property)
                if isinstance(member, StaticField):
                    return member.value
                return member
            if node.property in obj.methods:
                func = obj.methods[node.property]
                self._check_member_access(func, node.property)
                return func
            raise PropertyError(node.property, f"class '{obj.name}' (no such static member)")

        if isinstance(obj, EnumType):
            # 'values'/'fromValue' are Enum-level utilities, checked before
            # member lookup so they can't be shadowed by a same-named
            # member -- mirrors how Class exposes hasAttribute/getAttribute.
            if node.property == 'values':
                return lambda *args: self._enum_values_call(obj, args)
            if node.property == 'fromValue':
                return lambda *args: self._enum_from_value_call(obj, args)
            member = obj.members.get(node.property)
            if member is None:
                raise PropertyError(
                    node.property, f"enum '{obj.name}'",
                    known_properties=[m.name for m in obj.members_in_order] + ['values', 'fromValue'],
                )
            return member

        if isinstance(obj, EnumValue):
            if node.property == 'name':
                return obj.name
            if node.property == 'value':
                return obj.value
            raise PropertyError(
                node.property, f"enum member '{obj.enum_type.name}.{obj.name}'",
                known_properties=['name', 'value'],
            )

        if isinstance(obj, str):
            if node.property == 'length':
                return len(obj)

        if isinstance(obj, list):
            if node.property == 'length':
                return len(obj)
            # append()/push() are aliases of the same underlying mutation --
            # both are exposed as small lambdas that route through
            # _list_append_call so argument-count validation and the actual
            # mutation logic live in exactly one place.
            if node.property in ('append', 'push'):
                method_name = node.property
                return lambda *args: self._list_append_call(obj, method_name, args)
            if node.property == 'remove':
                return lambda *args: self._list_remove_call(obj, args)
            if node.property == 'contains':
                return lambda *args: self._list_contains_call(obj, args)
            if node.property == 'insert':
                return lambda *args: self._list_insert_call(obj, args)

        # Check if object has the property as an attribute
        if hasattr(obj, node.property):
            return getattr(obj, node.property)

        # Give a Bind-specific diagnosis when the property being accessed
        # is bind-only metadata (value/previous/origin/history/changes/
        # state/lastUpdate) but the target isn't actually a bind -- e.g.
        # `var score = 100; score.history`. Everything above this already
        # handles the case where obj really is a BindValue (its metadata
        # is real Python attributes, caught by the hasattr check just
        # above), so reaching here with one of these names means the
        # value genuinely isn't a bind.
        if node.property in BindValue.METADATA_PROPERTIES:
            raise BindMetadataAccessError(node.property, type(obj).__name__)

        known_properties = [name for name in dir(obj) if not name.startswith('_')]
        raise PropertyError(node.property, type(obj).__name__, known_properties=known_properties)

    def visit_ArrayAccess(self, node: ArrayAccess) -> Any:
        array = self.visit(node.array)
        index = self.visit(node.index)

        if isinstance(array, (list, str)):
            idx = self._resolve_index(index, len(array))
            return array[idx]

        if isinstance(array, dict):
            return array.get(index)

        if isinstance(array, Tensor):
            # t[i] on a rank>1 Tensor returns a sub-Tensor view; chained
            # bracket access (t[i][j]) covers full multidimensional
            # indexing without changing the single-index ArrayAccess grammar.
            try:
                return array[index]
            except BlazeError:
                raise
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot index into Tensor with {type(index).__name__}")

        raise BlazeRuntimeError(f"Cannot index into {type(array).__name__}")

    def visit_ThisExpression(self, node: ThisExpression) -> Any:
        if 'this' in self.current_scope:
            return self.current_scope['this']['value']
        raise StaticContextError("'this' is not defined in current context (are you inside a static function?)")

    def visit_SuperExpression(self, node: SuperExpression) -> Any:
        if 'this' not in self.current_scope:
            raise StaticContextError("'super' is not defined in current context (are you inside a static function?)")

        instance = self.current_scope['this']['value']
        if instance.cls.parent_class:
            return SuperProxy(instance.cls.parent_class, instance)
        raise BlazeRuntimeError(f"Class '{instance.cls.name}' has no parent class to call 'super' on")

    def visit_ImportStatement(self, node: ImportStatement) -> None:
        module_name = node.module

        if module_name == 'math':
            self._import_math(node)
        elif module_name == 'random':
            self._import_random(node)
        elif module_name == 'time':
            self._import_time(node)
        elif module_name == 'date':
            self._import_date(node)
        elif module_name == 'path':
            self._import_path(node)
        elif module_name == 'system':
            self._import_system(node)
        elif module_name == 'env':
            self._import_env(node)
        elif module_name == 'json':
            self._import_json(node)
        elif module_name == 'file':
            self._import_file_module(node)
        elif module_name == 'http':
            self._import_http(node)
        elif module_name == "httpserver":
            self._import_httpserver(node)
        elif module_name == "gui":
            self._import_gui(node)
        elif module_name == 'convert':
            self._import_convert(node)
        elif module_name == 'tensor':
            self._import_tensor(node)
        elif module_name.lower() in ('image', 'image'):
            self._import_image(node)
        elif module_name.lower() in ('video', 'video'):
            self._import_video(node)
        elif module_name == 'cli':
            self._import_cli(node)
        elif module_name == 'process':
            self._import_process(node)
        else:
            try:
                exports = self._load_module(module_name)
            except BlazeImportError as error:
                if not error.filename:
                    error.filename = self.filename
                    error.line = node.line
                    error.column = node.column
                    error.args = (error.format_error(),)
                raise
            if node.default_name:
                if 'default' not in exports:
                    raise BlazeImportError(f"Module '{module_name}' has no default export",
                                           node.line, node.column, self.filename)
                self._bind_import(node.default_name, exports['default'])
            elif node.namespace:
                self._bind_import(node.namespace, dict(exports))
            elif node.alias:
                # Legacy `Import package as API` remains a namespace import
                # for user packages just as it is for built-in modules.
                self._bind_import(node.alias, dict(exports))
            elif node.bindings:
                for exported, local in node.bindings:
                    if exported not in exports:
                        raise BlazeImportError(f"'{exported}' was not exported by {module_name}",
                                               node.line, node.column, self.filename)
                    self._bind_import(local, exports[exported])

        return None

    def visit_ExportStatement(self, node: ExportStatement) -> None:
        if self.current_exports is None:
            raise BlazeRuntimeError("Export statements can only be used while loading a module")
        if node.value is not None:
            if not node.is_default:
                raise BlazeRuntimeError("Only default exports may be expressions")
            export_name, value = 'default', self.visit(node.value)
        else:
            self.visit(node.declaration)
            name = getattr(node.declaration, 'name', None)
            if not name or name not in self.current_scope:
                raise BlazeRuntimeError("Exported declaration has no value")
            export_name, value = ('default' if node.is_default else name), self.current_scope[name]['value']
        if export_name in self.current_exports:
            message = "Only one default export is allowed." if node.is_default else f"Duplicate export '{name}'"
            raise BlazeImportError(message)
        self.current_exports[export_name] = value
        return None

    def _bind_import(self, name, value):
        self.current_scope[name] = {'value': value, 'constant': True}

    def _resolve_module_path(self, module_name):
        normalized = module_name.replace('\\', os.sep).replace('/', os.sep)
        candidate = Path(normalized)
        if not candidate.is_absolute():
            candidate = (Path(self.filename).parent if self.filename else Path.cwd()) / candidate
        if candidate.suffix == '':
            candidate = candidate.with_suffix('.blz')
        return candidate.resolve()

    def _load_module(self, module_name):
        from blazelang.package import load_installed_package, _safe_relative
        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser

        # 1. Check relative import within a package currently executing
        if getattr(self, "package_document", None) is not None and (module_name.startswith("./") or module_name.startswith("../")):
            pkg_meta = self.package_document["metadata"]
            pkg_name = pkg_meta["name"]
            current_rel = getattr(self, "package_rel_path", pkg_meta.get("main", "main.blz"))
            rel_dir = os.path.dirname(current_rel)
            norm_rel = os.path.normpath(os.path.join(rel_dir, module_name)).replace("\\", "/")
            if not norm_rel.endswith(".blz"):
                norm_rel += ".blz"
            if norm_rel in self.package_document["modules"]:
                key = f"blzp:{pkg_name}:{norm_rel}"
                if key in self.module_registry:
                    return self.module_registry[key]
                if key in self.loading_modules:
                    raise CircularImportError(f"Circular import in package {pkg_name}: {norm_rel}")
                source = self.package_document["modules"][norm_rel]
                self.loading_modules.append(key)
                try:
                    fake_file = f"package:{pkg_name}/{norm_rel}"
                    program = Parser(Lexer(source, fake_file).tokenize()).parse()
                    sub_interp = Interpreter(
                        module_registry=self.module_registry,
                        loading_modules=self.loading_modules,
                        filename=fake_file,
                        package_document=self.package_document
                    )
                    sub_interp.package_rel_path = norm_rel
                    sub_interp.current_exports = {}
                    sub_interp.interpret(program)
                    self.module_registry[key] = sub_interp.current_exports
                    return sub_interp.current_exports
                finally:
                    self.loading_modules.pop()

        # 2. Check if module_name resolves to an installed .blzp package or sub-module
        pkg_doc = load_installed_package(module_name)
        if pkg_doc is not None:
            pkg_meta = pkg_doc["metadata"]
            pkg_name = pkg_meta["name"]
            modules = pkg_doc["modules"]

            if "/" in module_name or "\\" in module_name:
                sub_path = module_name.replace("\\", "/").partition("/")[2]
                if not sub_path.endswith(".blz"):
                    sub_path += ".blz"
                target_rel = sub_path
            else:
                target_rel = pkg_meta.get("main", "main.blz")

            target_rel = _safe_relative(target_rel)
            if target_rel in modules:
                key = f"blzp:{pkg_name}:{target_rel}"
                if key in self.module_registry:
                    return self.module_registry[key]
                if key in self.loading_modules:
                    raise CircularImportError(f"Circular import in package {pkg_name}: {target_rel}")

                source = modules[target_rel]
                self.loading_modules.append(key)
                try:
                    fake_file = f"package:{pkg_name}/{target_rel}"
                    program = Parser(Lexer(source, fake_file).tokenize()).parse()
                    pkg_interp = Interpreter(
                        module_registry=self.module_registry,
                        loading_modules=self.loading_modules,
                        filename=fake_file,
                        package_document=pkg_doc
                    )
                    pkg_interp.package_rel_path = target_rel
                    pkg_interp.current_exports = {}
                    pkg_interp.interpret(program)
                    self.module_registry[key] = pkg_interp.current_exports
                    return pkg_interp.current_exports
                finally:
                    self.loading_modules.pop()

        # 3. Standard disk file-system module loading
        path = self._resolve_module_path(module_name)
        key = str(path)
        if key in self.module_registry:
            return self.module_registry[key]
        if key in self.loading_modules:
            chain = self.loading_modules[self.loading_modules.index(key):] + [key]
            readable = '\n'.join(
                ('' if i == 0 else '    ' * i + '↳ ') + Path(item).name
                for i, item in enumerate(chain)
            )
            raise CircularImportError(readable)
        if not path.is_file():
            error = BlazeImportError(f"Module file not found: {module_name}")
            if path.parent.is_dir():
                matches = get_close_matches(path.name, [item.name for item in path.parent.glob("*.blz")], n=1, cutoff=0.6)
                if matches:
                    error.hint = f"Did you mean '{matches[0]}' in {path.parent}?"
            raise error

        self.loading_modules.append(key)
        try:
            program = Parser(Lexer(path.read_text(encoding='utf-8'), str(path)).tokenize()).parse()
            module = Interpreter(self.module_registry, self.loading_modules, str(path))
            module.current_exports = {}
            module.interpret(program)
            self.module_registry[key] = module.current_exports
            return module.current_exports
        finally:
            self.loading_modules.pop()

    def visit_StringInterpolation(self, node: StringInterpolation) -> str:
        result = []
        for part in node.parts:
            if isinstance(part, StringLiteral):
                result.append(part.value)
            else:
                value = self.visit(part)
                result.append(self._format_value(value))
        return ''.join(result)

    # =====================
    # String Interpolation
    # =====================

    # A `{...}` span is only ever real BlazeLang interpolation syntax if its
    # contents look like an expression (identifier, dotted/bracket access,
    # a function call, an operator expression, etc). Arbitrary runtime string
    # values -- most importantly JSON produced by Json.Stringify() -- can
    # legitimately contain literal `{`, `}`, `:`, quotes and slashes (e.g.
    # `{"name":"Rohit","active":true}`, `{"url":"https://example.com"}`).
    # Those are NOT interpolation expressions, and running them through
    # _evaluate_embedded_expression corrupts them (stray backslashes,
    # dropped quotes/braces, etc) because that evaluator makes assumptions --
    # like "a string that starts and ends with a quote is a string literal"
    # -- that only hold for hand-written interpolation expressions, not for
    # JSON text that happens to be wrapped in braces. Detect that shape
    # up front and skip interpolation for it instead of trying to evaluate it.
    _JSON_LIKE_BRACE_CONTENT = re.compile(r'"\s*:\s*(?:"|-?\d|true\b|false\b|null\b|\{|\[)')

    def _interpolate_string(self, text: str) -> str:
        """
        Process string interpolation with support for:
        - Simple variables: {name}
        - Function calls: {Upper(text)}
        - Array access: {fruits[0]}
        - Nested function calls: {len(fruits)}
        - Chained access: {student.subjects[0]}
        - Arithmetic: {a + b}, {a % b}

        Runtime string values that merely CONTAIN braces (most notably JSON
        text returned by Json.Stringify()) are left untouched -- see
        _JSON_LIKE_BRACE_CONTENT above.
        """
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
                    expr = text[i+1:j-1].strip()

                    # Not a real interpolation expression -- e.g. JSON
                    # object/array content. Copy the span through verbatim,
                    # unmodified, instead of attempting to evaluate it.
                    if self._JSON_LIKE_BRACE_CONTENT.search(expr):
                        result.append(text[i:j])
                        i = j
                        continue

                    try:
                        # First try to evaluate as a complex expression
                        value = self._evaluate_embedded_expression(expr)

                        # Format the value properly
                        if isinstance(value, (Function, BoundMethod, Class, Instance)):
                            result.append(str(value))
                        else:
                            result.append(self._format_value(value))
                    except BlazeError:
                        # A genuine BlazeLang runtime error raised while
                        # evaluating an interpolated expression (undefined
                        # variable, type error, an error propagating out of
                        # a called function -- including one defined in an
                        # imported module) must be allowed to propagate with
                        # its real file/line/column intact, exactly like any
                        # other runtime error. Silently swallowing it here
                        # (the previous behavior) hid the error completely:
                        # Show("{BrokenFunction()}") would just print the
                        # literal text "{BrokenFunction()}" instead of
                        # surfacing the failure, so callers never saw a
                        # location -- or any diagnostic at all.
                        raise
                    except Exception:
                        # Genuinely not an evaluable expression (e.g. plain
                        # text that happens to be wrapped in braces) -- fall
                        # back to the original text rather than crashing.
                        result.append(f'{{{expr}}}')

                    i = j
                    continue

            result.append(text[i])
            i += 1

        return ''.join(result)

    def _format_value(self, value: Any) -> str:
        """Format a value for display"""
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return str(value).lower()
        # Integer and Float are now distinct Python types all the way from
        # the lexer/parser through arithmetic (see builtin_type / Bug 1), so
        # display must respect that distinction too: a Float that happens to
        # have a whole-number value (e.g. `1.25 + 2.75` -> 4.0) must still
        # print as "4.0", not silently collapse to "4" and look like an
        # Integer. Only a genuine Python int prints without a decimal point.
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            items = [self._format_value(item) for item in value]
            return '[' + ', '.join(items) + ']'
        if isinstance(value, dict):
            items = []
            for k, v in value.items():
                items.append(f"'{k}': {self._format_value(v)}")
            return '{' + ', '.join(items) + '}'
        if isinstance(value, (Function, BoundMethod, Class, Instance)):
            return str(value)
        return str(value)

    def _evaluate_embedded_expression(self, expr: str) -> Any:
        """
        Evaluate an expression embedded in a string interpolation `{...}`
        span by reusing the real BlazeLang Lexer and Parser, then running
        the resulting AST through the normal `self.visit` path -- exactly
        as if the expression had been written outside a string.

        Previously this duplicated a large part of the expression grammar
        by hand with regexes (arithmetic, comparisons, chained property /
        array access, function calls, ...). That duplicate grammar was
        incomplete and buggy in ways the real parser is not -- for example
        it treated the '.' in a float literal like `1.25` as the start of
        property access and routed the whole expression into the
        chained-access handler instead of arithmetic, so
        `{1.25 + 2.75}` silently failed to evaluate. It also had no concept
        of Class/Struct/Instance member resolution, so static members
        (`Counter.value`, `Counter.GetValue()`) and struct fields
        (`point.x`) inside interpolation could not be resolved the same
        way they are everywhere else in the language.

        Reusing the real Lexer/Parser/interpreter pipeline means every
        expression form supported by BlazeLang outside a string
        (arithmetic, comparisons, boolean logic, function calls, instance
        method calls, struct/class/static member access, chained access,
        indexing, literals, ...) is automatically supported inside `{...}`
        too, with identical semantics and error handling -- there is only
        one expression evaluator in the whole interpreter now.
        """
        if not expr or not expr.strip():
            return ''

        # Local import: avoids a module-level import cycle, since the
        # lexer/parser modules are otherwise independent of the interpreter.
        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser
        from blazelang.errors.error_handler import BlazeError as _BlazeBaseError

        try:
            tokens = Lexer(expr, self.filename).tokenize()
            expr_ast = Parser(tokens).parse_expression()
        except Exception:
            # Not a parseable expression (e.g. genuinely literal text that
            # happens to be wrapped in braces) -- leave it untouched rather
            # than raising out of string interpolation.
            return f'{{{expr}}}'

        try:
            return self.visit(expr_ast)
        except _BlazeBaseError:
            # A real BlazeLang runtime error (undefined variable, type
            # error, etc) from inside an interpolated expression should
            # surface exactly like it would anywhere else in the program.
            raise
        except Exception:
            return f'{{{expr}}}'

    # =====================
    # Helper Methods
    # =====================

    def is_truthy(self, value: Any) -> bool:
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

    def _import_standard_module(self, node, module, module_name):
        name = node.default_name or node.namespace or node.alias
        if name:
            self._bind_import(name, module)
            return
        for exported, local in node.bindings:
            if exported not in module:
                raise BlazeImportError(f"'{exported}' was not exported by {module_name}", node.line, node.column, self.filename)
            self._bind_import(local, module[exported])
        if not node.bindings:
            for exported, value in module.items():
                self._bind_import(exported, value)

    def _import_math(self, node):
        from blazelang.stdlib.math import create_math_module
        self._import_standard_module(node, create_math_module(), "math")

    def _import_random(self, node):
        from blazelang.stdlib.random import create_random_module
        self._import_standard_module(node, create_random_module(), "random")

    def _import_time(self, node):
        from blazelang.stdlib.time import create_time_module
        self._import_standard_module(node, create_time_module(), "time")

    def _import_date(self, node):
        from blazelang.stdlib.date import create_date_module
        self._import_standard_module(node, create_date_module(), "date")

    def _import_path(self, node):
        from blazelang.stdlib.path import create_path_module
        self._import_standard_module(node, create_path_module(), "path")

    def _import_system(self, node):
        from blazelang.stdlib.system import create_system_module
        self._import_standard_module(node, create_system_module(), "system")

    def _import_env(self, node):
        from blazelang.stdlib.env import create_env_module
        self._import_standard_module(node, create_env_module(), "env")

    def _import_convert(self, node):
        from blazelang.stdlib.convert import create_convert_module
        self._import_standard_module(node, create_convert_module(), "convert")

    def _import_tensor(self, node):
        from blazelang.stdlib.tensor import create_tensor_module
        self._import_standard_module(node, create_tensor_module(), "tensor")

    def _import_image(self, node):
        from blazelang.stdlib.image import create_image_module
        base_dir = Path(self.filename).parent if self.filename else Path.cwd()
        self._import_standard_module(node, create_image_module(base_dir), "image")

    def _import_video(self, node):
        from blazelang.stdlib.video import create_video_module
        base_dir = Path(self.filename).parent if self.filename else Path.cwd()
        self._import_standard_module(node, create_video_module(base_dir), "video")

    def _import_cli(self, node):
        from blazelang.stdlib.cli import create_cli_module
        self._import_standard_module(node, create_cli_module(self), "cli")

    def _import_process(self, node):
        from blazelang.stdlib.process import create_process_module
        self._import_standard_module(node, create_process_module(), "process")

    def _import_httpserver(self, node):
        from blazelang.stdlib.httpserver import create_httpserver_module

        self._import_standard_module(
            node,
            create_httpserver_module(self),
            "httpserver"
        )

    def _import_gui(self, node):
        from blazelang.stdlib.Gui import create_gui_module

        self._import_standard_module(
            node,
            create_gui_module(self),
            "gui"
        )

    def _import_json(self, node):
        """Bind the production JSON namespace and support legacy imports."""
        from blazelang.stdlib.json import create_json_module
        json_module = create_json_module()
        name = node.default_name or node.namespace or node.alias
        if name:
            self._bind_import(name, json_module)
            return
        for exported, local in node.bindings:
            if exported not in json_module:
                raise BlazeImportError(f"'{exported}' was not exported by json", node.line, node.column, self.filename)
            self._bind_import(local, json_module[exported])
        if not node.bindings:
            # Original Import json form keeps callable names in scope.
            for exported, value in json_module.items():
                self._bind_import(exported, value)

    def _import_file_module(self, node):
        from blazelang.stdlib.file import create_file_module
        base_dir = Path(self.filename).parent if self.filename else Path.cwd()
        file_module = create_file_module(base_dir)
        name = node.default_name or node.namespace or node.alias
        if name:
            self._bind_import(name, file_module)
            return
        for exported, local in node.bindings:
            if exported not in file_module:
                raise BlazeImportError(f"'{exported}' was not exported by file", node.line, node.column, self.filename)
            self._bind_import(local, file_module[exported])

    def _import_http(self, node):
        """Bind the built-in HTTP namespace for default or namespace imports."""
        from blazelang.stdlib.http import create_http_module
        base_dir = Path(self.filename).parent if self.filename else Path.cwd()
        http_module = create_http_module(base_dir)
        name = node.default_name or node.namespace or node.alias
        if name:
            self._bind_import(name, http_module)
            return
        for exported, local in node.bindings:
            if exported not in http_module:
                raise BlazeImportError(f"'{exported}' was not exported by http", node.line, node.column, self.filename)
            self._bind_import(local, http_module[exported])

    def _import_file(self, path: str, alias: str = None):
        print(f"Importing from file: {path}")

    # =====================
    # Built-in Functions
    # =====================

    def builtin_Show(self, *args):
        output = []
        for arg in args:
            if isinstance(arg, str):
                output.append(self._interpolate_string(arg))
            else:
                output.append(self._format_value(arg))
        print(*output)

    def builtin_Print(self, *args):
        output = []
        for arg in args:
            if isinstance(arg, str):
                output.append(self._interpolate_string(arg))
            else:
                output.append(self._format_value(arg))
        print(*output, end='')

    def builtin_Input(self, prompt: str = "") -> str:
        """Read one unmodified line from the terminal.

        Input deliberately always returns a string. EOF and terminal I/O errors
        are treated as an empty response so an interactive program can decide
        how to continue instead of crashing.
        """
        try:
            if isinstance(prompt, str):
                prompt_text = self._interpolate_string(prompt)
            else:
                prompt_text = self._format_value(prompt)
            if prompt_text:
                print(prompt_text, end='', flush=True)
            return input()
        except (EOFError, OSError):
            return ""

    def builtin_len(self, obj) -> int:
        return len(obj)

    def builtin_range(self, *args) -> range:
        """Return Python's compact lazy range instead of a materialized list."""
        if len(args) == 1:
            return range(int(args[0]))
        elif len(args) == 2:
            return range(int(args[0]), int(args[1]))
        elif len(args) == 3:
            return range(int(args[0]), int(args[1]), int(args[2]))
        return range(0)

    def builtin_type(self, obj) -> str:
        if isinstance(obj, BlazeFuture):
            return 'Future'
        if isinstance(obj, BindValue):
            # A Bind's outer runtime type is always 'bind', regardless of
            # what it currently wraps -- the wrapped value keeps its own
            # type internally (obj.value), reachable via score.value, and
            # type(score.value) still reports that original type normally.
            return 'bind'
        if obj is None:
            return 'Null'
        if isinstance(obj, bool):
            return 'Boolean'
        # NOTE: bool is checked above (before int) because bool is a
        # subclass of int in Python. From here on, Integer vs Float is
        # decided purely by the runtime value's Python type, which the
        # parser now preserves faithfully from the source literal (an
        # INTEGER token produces a Python int, a FLOAT token produces a
        # Python float) and arithmetic preserves via normal Python
        # int/float promotion. A "whole" float such as 1.0 must stay a
        # Float -- collapsing it to Integer by numeric value (the previous
        # behavior) is what made `type(1.0)` and `type(2.5)` report the
        # wrong thing.
        if isinstance(obj, int):
            return 'Integer'
        if isinstance(obj, float):
            return 'Float'
        if isinstance(obj, str):
            return 'String'
        if isinstance(obj, list):
            return 'Array'
        if isinstance(obj, dict):
            return 'Object'
        if isinstance(obj, Instance):
            return obj.cls.name
        if isinstance(obj, StructInstance):
            return obj.struct_type.name
        if isinstance(obj, EnumValue):
            return obj.enum_type.name
        if isinstance(obj, EnumType):
            return 'Enum'
        return type(obj).__name__

    def builtin_Upper(self, text: str) -> str:
        return str(text).upper()

    def builtin_Lower(self, text: str) -> str:
        return str(text).lower()

    def builtin_Trim(self, text: str) -> str:
        return str(text).strip()

    def builtin_Split(self, text: str, separator: str = " ") -> list:
        text = str(text)
        if separator == "":
            # Match JS-style behavior: split into individual characters
            return list(text)
        return text.split(separator)

    def builtin_Join(self, items: list, separator: str = "") -> str:
        return separator.join(str(item) for item in items)

    def builtin_Replace(self, text: str, old: str, new: str) -> str:
        return str(text).replace(old, new)

    def builtin_Contains(self, text: str, substring: str) -> bool:
        return substring in str(text)

    def builtin_StartsWith(self, text: str, prefix: str) -> bool:
        return str(text).startswith(prefix)

    def builtin_EndsWith(self, text: str, suffix: str) -> bool:
        return str(text).endswith(suffix)

    def builtin_Find(self, text: str, substring: str) -> int:
        return str(text).find(substring)

    def builtin_Reverse(self, items) -> list:
        if isinstance(items, str):
            return items[::-1]
        return list(reversed(items))

    def builtin_Random(self, min_val: float = 0, max_val: float = 1) -> float:
        import random
        if isinstance(min_val, int) and isinstance(max_val, int):
            return random.randint(min_val, max_val)
        return random.uniform(min_val, max_val)

    def builtin_Sleep(self, seconds: float):
        import time
        time.sleep(seconds)

    def builtin_Exit(self, code: int = 0):
        import sys
        sys.exit(code)

    def builtin_Int(self, value) -> int:
        return int(value)

    def builtin_Float(self, value) -> float:
        return float(value)

    def builtin_String(self, value) -> str:
        return str(value)

    def builtin_Bool(self, value) -> bool:
        return self.is_truthy(value)

    # =====================
    # eval() / evalFile()
    # =====================

    def builtin_eval(self, *args) -> Any:
        """`eval(sourceString)` -- parses `sourceString` as a single
        BlazeLang expression and evaluates it in the *current* scope (the
        same scope the `eval()` call itself is executing in), so it has
        access to whatever variables, functions, classes, Structs, enums,
        binds, properties, and methods are visible at that point -- exactly
        like writing that expression inline would.

        Reuses the same Lexer -> Parser -> Interpreter pipeline as the rest
        of the language (no Python eval()/exec() involved: see
        _run_eval_source / Parser.parse_single_expression), so every
        expression form BlazeLang supports elsewhere -- arithmetic,
        comparisons, boolean logic, string concatenation, indexing,
        property/method access, function calls, nested eval(), ... -- is
        automatically supported here too, with identical semantics and
        identical diagnostics for invalid input. Trailing tokens after a
        complete expression (`eval("10 + 20 garbage")`) are a ParserError,
        never silently discarded.
        """
        if len(args) != 1:
            raise ArgumentError('eval', 1, len(args))

        source = args[0]
        if not isinstance(source, str):
            raise ArgumentError.for_type_mismatch('eval', 'string', source)

        return self._run_eval_source(source)

    def builtin_evalFile(self, *args) -> Any:
        """`evalFile(path)` -- reads and executes a *complete* BlazeLang
        file (statements, not just a single expression) through the same
        Lexer -> Parser -> Interpreter pipeline, running it against this
        same interpreter's current scope -- so top-level `var`/`Function`/
        `Class`/`Struct`/`Enum` declarations in the evaluated file become
        visible to the caller afterward, the same way running that file's
        statements inline would. Subject to the same eval nesting-depth
        guard as eval()."""
        if len(args) != 1:
            raise ArgumentError('evalFile', 1, len(args))

        path = args[0]
        if not isinstance(path, str):
            raise ArgumentError.for_type_mismatch('evalFile', 'string', path)

        try:
            source = Path(path).read_text(encoding='utf-8')
        except FileNotFoundError:
            raise BlazeRuntimeError(f"evalFile(): file not found: '{path}'")
        except OSError as exc:
            raise BlazeRuntimeError(f"evalFile(): could not read '{path}': {exc}")

        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser

        self._enter_eval()
        try:
            tokens = Lexer(source, path).tokenize()
            program = Parser(tokens).parse()
            return self.visit(program)
        finally:
            self._exit_eval()

    def _run_eval_source(self, source: str) -> Any:
        """Shared `eval()` implementation: Lexer -> Parser.parse_single_expression()
        -> Interpreter.visit(), under the nesting-depth guard. Kept
        separate from builtin_eval so nested eval() calls (an expression
        whose evaluation calls eval() again) and any future internal
        callers share one depth-guarded code path."""
        # Local import: avoids a module-level import cycle, since the
        # lexer/parser modules are otherwise independent of the interpreter
        # (matches the existing pattern in _load_module /
        # _evaluate_embedded_expression).
        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser

        self._enter_eval()
        try:
            tokens = Lexer(source, self.filename or '<eval>').tokenize()
            expr = Parser(tokens).parse_single_expression()
            return self.visit(expr)
        finally:
            self._exit_eval()

    def _enter_eval(self) -> None:
        """Increment the eval nesting counter, raising once
        MAX_EVAL_DEPTH would be exceeded -- the guard against a string
        that (directly or through a chain of eval() calls) evaluates
        itself forever."""
        if self._eval_depth >= self.MAX_EVAL_DEPTH:
            raise EvalDepthExceededError(self.MAX_EVAL_DEPTH, filename=self.filename)
        self._eval_depth += 1

    def _exit_eval(self) -> None:
        self._eval_depth -= 1
