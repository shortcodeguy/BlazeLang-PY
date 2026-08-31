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
    visibility: str = 'default'
    had_explicit_modifier: bool = False
    is_static: bool = False
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class BindDeclaration(ASTNode):
    """bind declaration"""
    name: str
    value: Optional[Any] = None
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ExpressionStatement(ASTNode):
    """A statement consisting of a single expression"""
    expression: Any


@dataclass
class BlockStatement(ASTNode):
    """A block of statements enclosed in braces"""
    statements: List[ASTNode] = field(default_factory=list)


@dataclass
class IfStatement(ASTNode):
    """If/else if/else conditional statement"""
    condition: Any
    then_branch: BlockStatement
    else_if_branches: List[tuple] = field(default_factory=list)
    else_branch: Optional[BlockStatement] = None


@dataclass
class WhileStatement(ASTNode):
    """While loop statement"""
    condition: Any
    body: BlockStatement


@dataclass
class ForStatement(ASTNode):
    """For loop with range"""
    variable: str
    iterable: Any
    body: BlockStatement


@dataclass
class ForEachStatement(ASTNode):
    """For each loop over collection"""
    variable: str
    iterable: Any
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
    value: Optional[Any] = None


@dataclass
class ThrowStatement(ASTNode):
    """Throw an error"""
    value: Any


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
    is_meta: bool = False
    attributes: List['AttributeUsage'] = field(default_factory=list)


@dataclass
class MetaHookDeclaration(ASTNode):
    """A class-level Meta lifecycle hook."""
    hook_name: str
    parameters: List[str]
    body: BlockStatement


@dataclass
class ClassDeclaration(ASTNode):
    """Class declaration"""
    name: str
    members: List[ASTNode]
    parent_class: Optional[str] = None
    attributes: List['AttributeUsage'] = field(default_factory=list)


@dataclass
class ConstructorDeclaration(ASTNode):
    """Constructor declaration within a class"""
    parameters: List[str]
    body: BlockStatement


@dataclass
class StructField(ASTNode):
    """A single field inside a Struct declaration."""
    name: str
    default_value: Optional[Any] = None
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class StructDeclaration(ASTNode):
    """Struct declaration."""
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
    left: Any
    operator: str
    right: Any


@dataclass
class UnaryOperation(ASTNode):
    """Unary operation (-a, not a, etc.)"""
    operator: str
    operand: Any


@dataclass
class AwaitExpression(ASTNode):
    """Await an asynchronous expression."""
    value: Any


@dataclass
class Assignment(ASTNode):
    """Assignment expression (a = b, a += b, etc.)"""
    name: str
    value: Any
    operator: str = '='


@dataclass
class FunctionCall(ASTNode):
    """Function or method call"""
    callee: Any
    arguments: List[Any] = field(default_factory=list)


@dataclass
class FunctionExpression(ASTNode):
    """An anonymous function value, used by object/package APIs."""
    parameters: List[str]
    body: BlockStatement
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ArrayLiteral(ASTNode):
    """Array literal [1, 2, 3]"""
    elements: List[Any] = field(default_factory=list)


@dataclass
class ObjectLiteral(ASTNode):
    """Object literal {key: value}"""
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PropertyAccess(ASTNode):
    """Object property access (obj.prop)"""
    object: Any
    property: str


@dataclass
class ArrayAccess(ASTNode):
    """Array element access (arr[index])"""
    array: Any
    index: Any


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
    """Import statement."""
    module: str
    bindings: List[tuple] = field(default_factory=list)
    namespace: Optional[str] = None
    default_name: Optional[str] = None
    alias: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class ExportStatement(ASTNode):
    """An exported declaration."""
    declaration: Optional[ASTNode] = None
    value: Optional[Any] = None
    is_default: bool = False


@dataclass
class StringInterpolation(ASTNode):
    """String interpolation with expressions"""
    parts: List[Any] = field(default_factory=list)


@dataclass
class PropertyAssignment(ASTNode):
    """Property assignment like this.name = value or obj.prop = value"""
    object: Any
    property_name: str
    value: Any
    operator: str = '='


@dataclass
class ArrayElementAssignment(ASTNode):
    """Array element assignment like arr[0] = value"""
    array: Any
    index: Any
    value: Any
    operator: str = '='


@dataclass
class NamedArgument(ASTNode):
    """A name: value argument inside a call."""
    name: str
    value: Any = None


@dataclass
class EnumMember(ASTNode):
    """A single Enum member."""
    name: str
    value: Optional[Any] = None
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class EnumDeclaration(ASTNode):
    """Enum declaration."""
    name: str
    members: List[EnumMember] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


# === Custom Attributes ===

@dataclass
class AttributeDefinition(ASTNode):
    """Define @name or Define @name(param, ...)."""
    name: str
    parameters: List[str] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


@dataclass
class AttributeUsage(ASTNode):
    """A single @name or @name(args) usage."""
    name: str
    arguments: List[Any] = field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None


# === Reflect Userdata ===

@dataclass
class ReflectFieldSpec(ASTNode):
    """A field whitelist/requirement/blacklist tree used by `accept`,
    `expect`, and `reject` blocks inside `Reflect userdata(...)`.

    `fields` maps a field name to either `None` (a plain leaf field) or
    another `ReflectFieldSpec` (the field is expected to hold a nested
    object/array-of-objects, filtered by that nested spec)."""
    fields: Dict[str, Optional['ReflectFieldSpec']] = field(default_factory=dict)


@dataclass
class ReflectUserdata(ASTNode):
    """`Reflect <operation>(<source> { accept {...} expect {...} reject {...} })`

    A dedicated language construct -- not a library function call -- that
    evaluates `source` and returns a filtered/validated copy of it built
    from the optional `accept` (whitelist), `expect` (required-field
    check), and `reject` (blacklist, always wins over `accept`) specs.

    `operation` is the free-form identifier written directly after
    `Reflect` (e.g. `userdata`, `project`, `data`, `api`, `mydata`...). It
    is never hardcoded by the parser/interpreter -- any identifier is
    accepted and simply carried through as the operation's name, available
    to the runtime/diagnostics for context.
    """
    operation: str
    source: Any
    accept: Optional[ReflectFieldSpec] = None
    expect: Optional[ReflectFieldSpec] = None
    reject: Optional[ReflectFieldSpec] = None
    line: Optional[int] = None
    column: Optional[int] = None
    filename: Optional[str] = None
