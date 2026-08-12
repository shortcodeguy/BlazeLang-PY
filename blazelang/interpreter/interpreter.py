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
)
from typing import Any, Callable, Dict, List
import re
import math
from pathlib import Path
import os
from difflib import get_close_matches


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
                 attributes: Dict[str, list] = None):
        self.name = name
        self.parameters = parameters
        self.body = body
        self.is_meta = is_meta
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
                raise
            if hooks:
                run_hook('OnReturn', [method_token, result])
                run_hook('After', [method_token, result])
            # Legacy Meta functions are statement-like unless they explicitly
            # return a value (HTTP handlers rely on that established form).
            if self.is_meta and not returned_explicitly:
                return None
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


class Interpreter:
    """Tree-walking interpreter for BlazeLang"""

    def __init__(self, module_registry=None, loading_modules=None, filename=None):
        self.global_scope = {}
        self.current_scope = self.global_scope
        # Tracks which Class's method body is currently executing (None at top level
        # or inside a free function). Used to enforce `private` access control.
        self.current_class = None
        self.filename = os.path.abspath(filename) if filename else None
        self.module_registry = module_registry if module_registry is not None else {}
        self.loading_modules = loading_modules if loading_modules is not None else []
        self.current_exports = None
        self.call_stack = ["main()"]
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
        }

        for name, func in builtins.items():
            self.global_scope[name] = {
                'value': func,
                'constant': True
            }

    def interpret(self, node: ASTNode) -> Any:
        return self.visit(node)

    def visit(self, node: ASTNode) -> Any:
        if node is None:
            return None

        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        try:
            return visitor(node)
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
        while self.is_truthy(self.visit(node.condition)):
            try:
                result = self.visit(node.body)
            except BreakException:
                break
            except ContinueException:
                continue
        return result

    def visit_ForStatement(self, node: ForStatement) -> Any:
        iterable = self.visit(node.iterable)

        if isinstance(iterable, (list, range)):
            result = None
            for item in iterable:
                self.current_scope[node.variable] = {
                    'value': item,
                    'constant': False
                }
                try:
                    result = self.visit(node.body)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        if isinstance(iterable, str):
            result = None
            for char in iterable:
                self.current_scope[node.variable] = {
                    'value': char,
                    'constant': False
                }
                try:
                    result = self.visit(node.body)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        raise BlazeRuntimeError(f"Cannot iterate over {type(iterable).__name__}")

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
        )

        self.current_scope[node.name] = {
            'value': func,
            'constant': True
        }
        return None

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
        # Check for keywords that should be handled as statements
        if node.name == "continue":
            raise ContinueException()
        if node.name == "break":
            raise BreakException()

        if node.name in self.current_scope:
            return self.current_scope[node.name]['value']

        if node.name in self.global_scope:
            return self.global_scope[node.name]['value']

        error = BlazeRuntimeError(f"Undefined variable '{node.name}'")
        known_names = list(self.current_scope) + list(self.global_scope)
        matches = get_close_matches(node.name, known_names, n=1, cutoff=0.6)
        if matches:
            error.hint = f"Did you mean '{matches[0]}'?"
        raise error

    def visit_Assignment(self, node: Assignment) -> Any:
        value = self.visit(node.value)

        target_scope = None
        if node.name in self.current_scope:
            target_scope = self.current_scope
        elif node.name in self.global_scope:
            target_scope = self.global_scope
        else:
            self.current_scope[node.name] = {
                'value': None,
                'constant': False
            }
            target_scope = self.current_scope

        if target_scope[node.name]['constant']:
            raise ImmutableError(node.name)

        if node.operator == '=':
            target_scope[node.name]['value'] = value
        elif node.operator == '+=':
            target_scope[node.name]['value'] += value
        elif node.operator == '-=':
            target_scope[node.name]['value'] -= value
        elif node.operator == '*=':
            target_scope[node.name]['value'] *= value
        elif node.operator == '/=':
            target_scope[node.name]['value'] /= value

        return target_scope[node.name]['value']

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

        return value

    def visit_ArrayElementAssignment(self, node) -> Any:
        """Handle array element assignment like arr[0] = value"""
        array = self.visit(node.array)
        index = self.visit(node.index)
        value = self.visit(node.value)

        if isinstance(array, list):
            idx = int(index)
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

        raise BlazeRuntimeError(f"Cannot assign to index of {type(array).__name__}")

    def visit_BinaryOperation(self, node: BinaryOperation) -> Any:
        left = self.visit(node.left)

        # Short-circuit evaluation for 'and' / '&&'
        if node.operator in ('and', '&&'):
            if not self.is_truthy(left):
                return left
            return self.visit(node.right)

        # Short-circuit evaluation for 'or' / '||'
        if node.operator in ('or', '||'):
            if self.is_truthy(left):
                return left
            return self.visit(node.right)

        right = self.visit(node.right)

        # String concatenation
        if node.operator == '+':
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            try:
                return left + right
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '+' to {type(left).__name__} and {type(right).__name__}")

        operations = {
            '-': lambda a, b: a - b,
            '*': lambda a, b: a * b,
            '/': lambda a, b: a / b if b != 0 else (_ for _ in ()).throw(BlazeZeroDivisionError()),
            '%': lambda a, b: a % b if b != 0 else (_ for _ in ()).throw(BlazeZeroDivisionError()),
            '**': lambda a, b: a ** b,
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b,
            '>': lambda a, b: a > b,
            '<': lambda a, b: a < b,
            '>=': lambda a, b: a >= b,
            '<=': lambda a, b: a <= b,
        }

        if node.operator in operations:
            try:
                return operations[node.operator](left, right)
            except BlazeError:
                raise
            except (TypeError, ValueError):
                raise BlazeTypeError(f"Cannot apply operator '{node.operator}' to {type(left).__name__} and {type(right).__name__}")

        raise BlazeRuntimeError(f"Unknown operator '{node.operator}'")

    def visit_UnaryOperation(self, node: UnaryOperation) -> Any:
        operand = self.visit(node.operand)

        if node.operator == '-':
            return -operand
        elif node.operator == 'not':
            return not self.is_truthy(operand)

        raise BlazeRuntimeError(f"Unknown unary operator '{node.operator}'")

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

        # Handle built-in Python callables
        if callable(callee) and not isinstance(callee, Function) and not isinstance(callee, Class):
            return callee(*arguments)

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

        if isinstance(obj, str):
            if node.property == 'length':
                return len(obj)

        if isinstance(obj, list):
            if node.property == 'length':
                return len(obj)

        # Check if object has the property as an attribute
        if hasattr(obj, node.property):
            return getattr(obj, node.property)

        raise PropertyError(node.property, type(obj).__name__)

    def visit_ArrayAccess(self, node: ArrayAccess) -> Any:
        array = self.visit(node.array)
        index = self.visit(node.index)

        if isinstance(array, (list, str)):
            idx = int(index)
            try:
                return array[idx]
            except IndexError:
                raise BlazeIndexError(idx, len(array))

        if isinstance(array, dict):
            return array.get(index)

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
        elif module_name == 'convert':
            self._import_convert(node)
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
        self.visit(node.declaration)
        name = getattr(node.declaration, 'name', None)
        if not name or name not in self.current_scope:
            raise BlazeRuntimeError("Exported declaration has no value")
        export_name = 'default' if node.is_default else name
        if export_name in self.current_exports:
            message = "Only one default export is allowed." if node.is_default else f"Duplicate export '{name}'"
            raise BlazeImportError(message)
        self.current_exports[export_name] = self.current_scope[name]['value']
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
        from blazelang.lexer.lexer import Lexer
        from blazelang.parser.parser import Parser
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
                    except Exception as e:
                        # If evaluation fails, keep the original expression
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
        if isinstance(value, float) and math.isfinite(value) and value == int(value):
            return str(int(value))
        if isinstance(value, (int, float)):
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
        Evaluate an expression embedded in string interpolation
        Handles chained expressions like student.subjects[0], a % b
        """
        if not expr:
            return ''

        expr = expr.strip()

        # Handle function calls: FuncName(args)
        # Must check this first since it can contain dots and brackets
        func_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)$', expr)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2).strip()

            # Parse arguments
            args = self._parse_embedded_args(args_str)

            # Get the function from scope
            func = None
            if func_name in self.current_scope:
                func = self.current_scope[func_name]['value']
            elif func_name in self.global_scope:
                func = self.global_scope[func_name]['value']

            if func and callable(func):
                # Evaluate each argument
                evaluated_args = []
                for arg in args:
                    # Try to evaluate as expression first
                    try:
                        evaluated_args.append(self._evaluate_embedded_expression(arg))
                    except:
                        # If that fails, try as simple variable
                        if arg in self.current_scope:
                            evaluated_args.append(self.current_scope[arg]['value'])
                        elif arg in self.global_scope:
                            evaluated_args.append(self.global_scope[arg]['value'])
                        else:
                            evaluated_args.append(arg)

                # Call the function
                if isinstance(func, Function):
                    return func(self, evaluated_args)
                else:
                    # Built-in functions
                    try:
                        result = func(*evaluated_args)
                        return result
                    except Exception as e:
                        return f'{{Error: {str(e)}}}'
            else:
                return f'{{Unknown function: {func_name}}}'

        # Handle chained property/array access: var.prop.subprop[0]
        if '.' in expr or '[' in expr:
            return self._evaluate_chained_expression(expr)

        # Handle logical operators
        logic_match = self._match_operator_outside_brackets(expr, ['and', 'or'])
        if logic_match:
            left_expr = logic_match[0].strip()
            op = logic_match[1]
            right_expr = logic_match[2].strip()

            left = self._evaluate_embedded_expression(left_expr)

            if op == 'and':
                if not self.is_truthy(left):
                    return left
                return self._evaluate_embedded_expression(right_expr)
            elif op == 'or':
                if self.is_truthy(left):
                    return left
                return self._evaluate_embedded_expression(right_expr)

        # Handle comparison operators
        comp_match = self._match_operator_outside_brackets(expr, ['==', '!=', '>=', '<=', '>', '<'])
        if comp_match:
            left_expr = comp_match[0].strip()
            op = comp_match[1]
            right_expr = comp_match[2].strip()

            left = self._evaluate_embedded_expression(left_expr)
            right = self._evaluate_embedded_expression(right_expr)

            comparisons = {
                '==': lambda a, b: a == b,
                '!=': lambda a, b: a != b,
                '>': lambda a, b: a > b,
                '<': lambda a, b: a < b,
                '>=': lambda a, b: a >= b,
                '<=': lambda a, b: a <= b,
            }
            if op in comparisons:
                return comparisons[op](left, right)

        # Handle arithmetic: a + b, a - b, a * b, a / b, a % b
        arith_match = self._match_operator_outside_brackets(expr, ['+', '-', '*', '/', '%'])
        if arith_match:
            left_expr = arith_match[0].strip()
            op = arith_match[1]
            right_expr = arith_match[2].strip()

            left = self._evaluate_embedded_expression(left_expr)
            right = self._evaluate_embedded_expression(right_expr)

            try:
                # Handle string concatenation with +
                if isinstance(left, str) or isinstance(right, str):
                    if op == '+':
                        return str(left) + str(right)
                    raise ValueError("Cannot perform arithmetic on strings")

                # Convert to numbers
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

        # Handle not operator
        if expr.startswith('not '):
            inner = expr[4:].strip()
            value = self._evaluate_embedded_expression(inner)
            return not self.is_truthy(value)

        # Simple variable lookup - check current scope first
        if expr in self.current_scope:
            return self.current_scope[expr]['value']

        # Then check global scope
        if expr in self.global_scope:
            return self.global_scope[expr]['value']

        # Handle boolean literals
        if expr == 'true':
            return True
        if expr == 'false':
            return False
        if expr == 'null':
            return None

        # Handle numeric literals
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # Handle string literals
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # If nothing matches, return the expression as a string
        return f'{{{expr}}}'

    def _evaluate_chained_expression(self, expr: str) -> Any:
        """
        Evaluate chained property and array access
        Example: student.subjects[0], Reverse(fruits)[0]
        """
        # First check if it starts with a function call
        func_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)(.*)$', expr)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2).strip()
            rest = func_match.group(3).strip()

            args = self._parse_embedded_args(args_str)

            func = None
            if func_name in self.current_scope:
                func = self.current_scope[func_name]['value']
            elif func_name in self.global_scope:
                func = self.global_scope[func_name]['value']

            if func and callable(func):
                evaluated_args = []
                for arg in args:
                    try:
                        evaluated_args.append(self._evaluate_embedded_expression(arg))
                    except:
                        if arg in self.current_scope:
                            evaluated_args.append(self.current_scope[arg]['value'])
                        elif arg in self.global_scope:
                            evaluated_args.append(self.global_scope[arg]['value'])
                        else:
                            evaluated_args.append(arg)

                if isinstance(func, Function):
                    value = func(self, evaluated_args)
                else:
                    value = func(*evaluated_args)

                # Process the rest of the chain
                if rest:
                    return self._process_chain(value, rest)
                return value

        # Tokenize the expression for property/array access
        tokens = []
        current = ''
        i = 0

        while i < len(expr):
            if expr[i] == '.':
                if current:
                    tokens.append(('id', current))
                    current = ''
                i += 1
                prop = ''
                while i < len(expr) and (expr[i].isalnum() or expr[i] == '_'):
                    prop += expr[i]
                    i += 1
                if prop:
                    tokens.append(('dot', prop))
            elif expr[i] == '[':
                if current:
                    tokens.append(('id', current))
                    current = ''
                i += 1
                bracket_depth = 1
                index_expr = ''
                while i < len(expr) and bracket_depth > 0:
                    if expr[i] == '[':
                        bracket_depth += 1
                    elif expr[i] == ']':
                        bracket_depth -= 1
                        if bracket_depth > 0:
                            index_expr += expr[i]
                    else:
                        index_expr += expr[i]
                    i += 1
                tokens.append(('bracket', index_expr.strip()))
            else:
                current += expr[i]
                i += 1

        if current:
            tokens.append(('id', current))

        if not tokens:
            return f'{{{expr}}}'

        # Get initial value
        first_token = tokens[0]
        if first_token[0] == 'id':
            value = None
            if first_token[1] in self.current_scope:
                value = self.current_scope[first_token[1]]['value']
            elif first_token[1] in self.global_scope:
                value = self.global_scope[first_token[1]]['value']

            if value is None:
                return f'{{{expr}}}'
        else:
            return f'{{{expr}}}'

        # Follow the chain
        for token_type, token_value in tokens[1:]:
            if token_type == 'dot':
                if isinstance(value, dict):
                    value = value.get(token_value)
                elif isinstance(value, Instance):
                    value = value.get(token_value)
                elif isinstance(value, list):
                    if token_value == 'length':
                        value = len(value)
                    else:
                        # Try to get attribute
                        if hasattr(value, token_value):
                            value = getattr(value, token_value)
                elif isinstance(value, str):
                    if token_value == 'length':
                        value = len(value)
                else:
                    return f'{{{expr}}}'
            elif token_type == 'bracket':
                index = self._evaluate_embedded_expression(token_value)
                if isinstance(value, (list, str)):
                    try:
                        value = value[int(index)]
                    except (ValueError, IndexError):
                        return f'{{{expr}}}'
                elif isinstance(value, dict):
                    value = value.get(index)
                else:
                    return f'{{{expr}}}'

        return value

    def _process_chain(self, value: Any, chain: str) -> Any:
        """Process property/array access chain on a value"""
        i = 0
        while i < len(chain):
            if chain[i] == '.':
                i += 1
                prop = ''
                while i < len(chain) and (chain[i].isalnum() or chain[i] == '_'):
                    prop += chain[i]
                    i += 1

                if isinstance(value, dict):
                    value = value.get(prop)
                elif isinstance(value, Instance):
                    value = value.get(prop)
                elif isinstance(value, list) and prop == 'length':
                    value = len(value)
                elif isinstance(value, str) and prop == 'length':
                    value = len(value)
                else:
                    return value
            elif chain[i] == '[':
                i += 1
                bracket_depth = 1
                index_expr = ''
                while i < len(chain) and bracket_depth > 0:
                    if chain[i] == '[':
                        bracket_depth += 1
                    elif chain[i] == ']':
                        bracket_depth -= 1
                        if bracket_depth > 0:
                            index_expr += chain[i]
                    else:
                        index_expr += chain[i]
                    i += 1

                index = self._evaluate_embedded_expression(index_expr.strip())
                if isinstance(value, (list, str)):
                    try:
                        value = value[int(index)]
                    except (ValueError, IndexError):
                        return value
                elif isinstance(value, dict):
                    value = value.get(index)
            else:
                i += 1

        return value

    def _match_operator_outside_brackets(self, expr: str, operators: List[str]) -> tuple:
        """
        Find an operator that is not inside brackets or parentheses
        Returns (left, operator, right) or None
        """
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
                    if expr[i:i+len(op)] == op:
                        if op.isalpha():
                            before_ok = i == 0 or not expr[i-1].isalnum()
                            after_ok = i+len(op) >= len(expr) or not expr[i+len(op)].isalnum()
                            if before_ok and after_ok:
                                return (expr[:i], op, expr[i+len(op):])
                        else:
                            return (expr[:i], op, expr[i+len(op):])
                i += 1
            else:
                i += 1

        return None

    def _parse_embedded_args(self, args_str: str) -> List[str]:
        """Parse argument string from embedded expression"""
        if not args_str:
            return []

        args = []
        current = ''
        paren_depth = 0
        bracket_depth = 0
        in_string = False
        string_char = None

        for char in args_str:
            if char in ['"', "'"] and not in_string:
                in_string = True
                string_char = char
                current += char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                current += char
            elif in_string:
                current += char
            elif char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == '[':
                bracket_depth += 1
                current += char
            elif char == ']':
                bracket_depth -= 1
                current += char
            elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                args.append(current.strip())
                current = ''
            else:
                current += char

        if current.strip():
            args.append(current.strip())

        return args

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

    def _import_httpserver(self, node):
        from blazelang.stdlib.httpserver import create_httpserver_module

        self._import_standard_module(
            node,
            create_httpserver_module(self),
            "httpserver"
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

    def builtin_range(self, *args) -> list:
        if len(args) == 1:
            return list(range(int(args[0])))
        elif len(args) == 2:
            return list(range(int(args[0]), int(args[1])))
        elif len(args) == 3:
            return list(range(int(args[0]), int(args[1]), int(args[2])))
        return []

    def builtin_type(self, obj) -> str:
        if obj is None:
            return 'Null'
        if isinstance(obj, bool):
            return 'Boolean'
        if isinstance(obj, int):
            return 'Integer'
        if isinstance(obj, float):
            if float(obj) == int(obj):
                return 'Integer'
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