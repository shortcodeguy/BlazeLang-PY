"""
Abstract Syntax Tree node definitions for BlazeLang
All AST nodes that represent language constructs
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


class ASTNode:
    """Base class for all AST nodes"""
    def accept(self, visitor):
        """Accept a visitor for the visitor pattern"""
        method_name = f'visit_{type(self).__name__}'
        visitor_method = getattr(visitor, method_name, visitor.generic_visit)
        return visitor_method(self)


# === Program Structure ===

@dataclass
class Program(ASTNode):
    """Root node representing an entire program"""
    statements: List[ASTNode] = field(default_factory=list)


# === Statements ===

@dataclass
class VariableDeclaration(ASTNode):
    """Variable or constant declaration"""
    name: str
    value: Optional[Any] = None
    is_constant: bool = False
    type_annotation: Optional[str] = None
    # 'public', 'private', or 'default' (no modifier written). Only enforced
    # for class-level fields; plain local/global 'var'/'constant' declarations
    # keep their existing unrestricted behavior regardless of this value.
    visibility: str = 'default'
    had_explicit_modifier: bool = False
    is_static: bool = False
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ExpressionStatement(ASTNode):
    """A statement consisting of a single expression"""
    expression: Any  # Expression node


@dataclass
class BlockStatement(ASTNode):
    """A block of statements enclosed in braces"""
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class IfStatement(ASTNode):
    """If/else if/else conditional statement"""
    condition: Any  # Expression node
    then_branch: BlockStatement
    else_if_branches: List[tuple] = field(default_factory=list)  # List of (condition, BlockStatement)
    else_branch: Optional[BlockStatement] = None


@dataclass
class WhileStatement(ASTNode):
    """While loop statement"""
    condition: Any  # Expression node
    body: BlockStatement


@dataclass
class ForStatement(ASTNode):
    """For loop with range"""
    variable: str
    iterable: Any  # Expression node
    body: BlockStatement


@dataclass
class ForEachStatement(ASTNode):
    """For each loop over collection"""
    variable: str
    iterable: Any  # Expression node
    body: BlockStatement


@dataclass
class BreakStatement(ASTNode):
    """Break statement to exit loops"""
    pass


@dataclass
class ContinueStatement(ASTNode):
    """Continue statement to skip iteration"""
    pass


@dataclass
class ReturnStatement(ASTNode):
    """Return statement from function"""
    value: Optional[Any] = None  # Expression node


@dataclass
class ThrowStatement(ASTNode):
    """Throw an error"""
    value: Any  # Expression node


@dataclass
class TryCatchStatement(ASTNode):
    """Try/catch/finally error handling"""
    try_block: BlockStatement
    catch_block: BlockStatement
    error_var: str
    finally_block: Optional[BlockStatement] = None


# === Declarations ===

@dataclass
class FunctionDeclaration(ASTNode):
    """Function or Meta declaration"""
    name: str
    parameters: List[str]
    body: BlockStatement
    return_type: Optional[str] = None
    is_async: bool = False
    is_static: bool = False
    access_modifier: str = 'public'
    is_meta: bool = False  # True for Meta, False for Function
    # Custom attributes attached via '@name' / '@name(args)' immediately
    # before this declaration (e.g. @logged, @role("admin")). Empty when
    # none were written. Purely metadata -- attaching an attribute never
    # executes anything on its own.
    attributes: List['AttributeUsage'] = field(default_factory=list)


@dataclass
class MetaHookDeclaration(ASTNode):
    """A class-level Meta lifecycle hook.

    Hooks are deliberately separate from ordinary ``Meta Name(...)`` methods so
    the latter retain their established behaviour.  The supported hook names
    are OnCall, Before, OnReturn, After, and OnError.
    """
    hook_name: str
    parameters: List[str]
    body: BlockStatement


@dataclass
class ClassDeclaration(ASTNode):
    """Class declaration"""
    name: str
    members: List[ASTNode]
    parent_class: Optional[str] = None
    # Custom attributes attached via '@name' / '@name(args)' immediately
    # before this declaration. See FunctionDeclaration.attributes.
    attributes: List['AttributeUsage'] = field(default_factory=list)


@dataclass
class ConstructorDeclaration(ASTNode):
    """Constructor declaration within a class"""
    parameters: List[str]
    body: BlockStatement


@dataclass
class StructField(ASTNode):
    """A single field inside a Struct declaration, in declaration order.
    ``default_value`` is the unevaluated expression node (or None if the
    field has no explicit default, in which case it defaults to null)."""
    name: str
    default_value: Optional[Any] = None
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class StructDeclaration(ASTNode):
    """Struct declaration: a lightweight, data-only type independent of the
    Class system. Struct does not support inheritance, constructors,
    methods, or visibility modifiers -- it only declares fields."""
    name: str
    fields: List[StructField] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


# === Expressions ===

@dataclass
class NumberLiteral(ASTNode):
    """Numeric literal (integer or float)"""
    value: float


@dataclass
class StringLiteral(ASTNode):
    """String literal"""
    value: str


@dataclass
class BooleanLiteral(ASTNode):
    """Boolean literal (true/false)"""
    value: bool


@dataclass
class NullLiteral(ASTNode):
    """Null literal"""
    pass


@dataclass
class Identifier(ASTNode):
    """Variable or function identifier"""
    name: str


@dataclass
class BinaryOperation(ASTNode):
    """Binary operation (a + b, a > b, etc.)"""
    left: Any  # Expression node
    operator: str
    right: Any  # Expression node


@dataclass
class UnaryOperation(ASTNode):
    """Unary operation (-a, not a, etc.)"""
    operator: str
    operand: Any  # Expression node


@dataclass
class Assignment(ASTNode):
    """Assignment expression (a = b, a += b, etc.)"""
    name: str
    value: Any  # Expression node
    operator: str = '='


@dataclass
class FunctionCall(ASTNode):
    """Function or method call"""
    callee: Any  # Expression node
    arguments: List[Any] = field(default_factory=list)  # List of Expression nodes


@dataclass
class ArrayLiteral(ASTNode):
    """Array literal [1, 2, 3]"""
    elements: List[Any] = field(default_factory=list)  # List of Expression nodes


@dataclass
class ObjectLiteral(ASTNode):
    """Object literal {key: value}"""
    properties: Dict[str, Any] = field(default_factory=dict)  # Dict of name: Expression


@dataclass
class PropertyAccess(ASTNode):
    """Object property access (obj.prop)"""
    object: Any  # Expression node
    property: str


@dataclass
class ArrayAccess(ASTNode):
    """Array element access (arr[index])"""
    array: Any  # Expression node
    index: Any  # Expression node


@dataclass
class ThisExpression(ASTNode):
    """'this' keyword expression"""
    pass


@dataclass
class SuperExpression(ASTNode):
    """'super' keyword expression"""
    pass


@dataclass
class ImportStatement(ASTNode):
    """Import statement. ``bindings`` contains (exported_name, local_name)."""
    module: str
    bindings: List[tuple] = field(default_factory=list)
    namespace: Optional[str] = None
    default_name: Optional[str] = None
    # Kept for compatibility with the original ``Import math as Math`` syntax.
    alias: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ExportStatement(ASTNode):
    """An exported declaration."""
    declaration: ASTNode
    is_default: bool = False


@dataclass
class StringInterpolation(ASTNode):
    """String interpolation with expressions"""
    parts: List[Any] = field(default_factory=list)  # Mix of StringLiteral and Expression nodes

@dataclass
class PropertyAssignment(ASTNode):
    """Property assignment like this.name = value or obj.prop = value"""
    object: Any  # Expression node (usually ThisExpression or Identifier)
    property_name: str
    value: Any  # Expression node
    operator: str = '='

@dataclass
class ArrayElementAssignment(ASTNode):
    """Array element assignment like arr[0] = value"""
    array: Any  # Expression node
    index: Any  # Expression node
    value: Any  # Expression node
    operator: str = '='


@dataclass
class NamedArgument(ASTNode):
    """A `name: value` argument inside a call's argument list, e.g.
    `User(name: "Rohit", age: 13)`. Reused by the general call-argument
    parser so any call site can mix positional and named arguments; today
    only Struct construction actually interprets named arguments, other
    callables reject them with a clear error rather than silently
    misusing them."""
    name: str
    value: Any = None


# === Custom Attributes ===

@dataclass
class AttributeDefinition(ASTNode):
    """`Define @name` or `Define @name(param, ...)`.

    Declares an attribute name (and, optionally, its parameter list) so it
    can later be attached to a Function/Meta/Class declaration with
    `@name` / `@name(args)`. Declaring an attribute never executes
    anything -- it only registers the name/arity for later use and for
    Meta inspection.
    """
    name: str
    parameters: List[str] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class AttributeUsage(ASTNode):
    """A single `@name` or `@name(args)` attached to a Function, Meta, or
    Class declaration. `arguments` holds unevaluated expression nodes --
    they are evaluated once, when the declaration they decorate runs, just
    like any other expression in that scope."""
    name: str
    arguments: List[Any] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None