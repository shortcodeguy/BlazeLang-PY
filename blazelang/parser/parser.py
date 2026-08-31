"""
Recursive Descent Parser for BlazeLang
Converts token stream into Abstract Syntax Tree
"""

from blazelang.tokens.token_types import TokenType
from blazelang.errors.error_handler import (
    ParserError,
    DuplicateStructFieldError,
    InvalidStructFieldError,
    StructMethodNotAllowedError,
    StructConstructorNotAllowedError,
    StructInheritanceError,
    InvalidAttributeSyntaxError,
    UndefinedAttributeError,
    DuplicateAttributeDefinitionError,
    DuplicateAttributeUsageError,
    InvalidAttributeArgumentsError,
    AttributeTargetError,
    DuplicateEnumMemberError,
    InvalidEnumMemberError,
    InvalidEnumValueError,
)
from blazelang.ast.ast_nodes import *


class Parser:
    """Recursive descent parser for BlazeLang"""
    
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.position = 0
        self.current_token = tokens[0] if tokens else None
        self.filename = self.current_token.filename if self.current_token else None
        # name -> list of declared parameter names, populated by 'Define @name(...)'.
        self.defined_attributes = {}
    
    def advance(self):
        """Move to next token"""
        self.position += 1
        if self.position < len(self.tokens):
            self.current_token = self.tokens[self.position]
        else:
            self.current_token = None

    @staticmethod
    def _tag(node, token):
        """Attach source coordinates without expanding every AST dataclass."""
        node.line, node.column, node.filename = token.line, token.column, token.filename
        return node

    @staticmethod
    def _binary(left, operator, right, token=None):
        """Fold deterministic literal arithmetic during parsing.

        Division/modulo by zero stay as AST operations so they retain their
        established BlazeLang runtime diagnostic rather than becoming parser
        errors.  All other folds use Python's same primitive semantics.
        """
        literal_types = (NumberLiteral, StringLiteral, BooleanLiteral)
        if isinstance(left, literal_types) and isinstance(right, literal_types):
            try:
                a, b = left.value, right.value
                if operator == '+': value = str(a) + str(b) if isinstance(a, str) or isinstance(b, str) else a + b
                elif operator == '-': value = a - b
                elif operator == '*': value = a * b
                elif operator == '/' and b != 0: value = a / b
                elif operator == '%' and b != 0: value = a % b
                elif operator in ('**', '^'): value = a ** b
                elif operator == '==': value = a == b
                elif operator == '!=': value = a != b
                elif operator == '>': value = a > b
                elif operator == '<': value = a < b
                elif operator == '>=': value = a >= b
                elif operator == '<=': value = a <= b
                else: raise ValueError
                node = BooleanLiteral(value) if isinstance(value, bool) else (StringLiteral(value) if isinstance(value, str) else NumberLiteral(value))
                return Parser._tag(node, token) if token else node
            except (TypeError, ValueError, OverflowError):
                pass
        node = BinaryOperation(left=left, operator=operator, right=right)
        return Parser._tag(node, token) if token else node
    
    def peek(self, offset: int = 1):
        """Look ahead without consuming"""
        peek_pos = self.position + offset
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        return None
    
    def expect(self, token_type: TokenType):
        """Expect and consume a specific token type"""
        if self.current_token and self.current_token.type == token_type:
            token = self.current_token
            self.advance()
            return token
        
        found = self.current_token.type.name if self.current_token else 'EOF'
        line = self.current_token.line if self.current_token else 0
        col = self.current_token.column if self.current_token else 0
        
        raise ParserError(
            f"Expected {token_type.name}, but found {found}",
            line, col
        )
    
    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types"""
        return self.current_token and self.current_token.type in token_types
    
    def parse(self) -> Program:
        """Parse the entire program"""
        try:
            statements = []
            while self.current_token and self.current_token.type != TokenType.EOF:
                statement = self.parse_statement()
                if statement:
                    statements.append(statement)
            self._validate_exports(statements)
            program = Program(statements=statements)
            program.warnings = self._collect_warnings(statements)
            return program
        except ParserError as error:
            # Parser helpers know the token position but not always its file.
            # Complete that information here for a useful command-line error.
            if not error.filename:
                token = self.current_token
                error.filename = self.filename
                error.line = error.line or (token.line if token else None)
                error.column = error.column or (token.column if token else None)
                error.args = (error.format_error(),)
            raise

    def _validate_exports(self, statements):
        """Catch duplicate/default exports before any module executes."""
        names = set()
        default_seen = False
        for statement in statements:
            if not isinstance(statement, ExportStatement):
                continue
            if statement.is_default:
                if default_seen:
                    raise ParserError("Only one default export is allowed.")
                default_seen = True
                continue
            # Expression exports only exist for the default export and were
            # handled above. Named exports still require a declaration name.
            name = getattr(statement.declaration, 'name', None)
            if name in names:
                raise ParserError(f"Duplicate export '{name}'")
            names.add(name)

    def _collect_warnings(self, statements):
        """Small static checks that do not alter program execution."""
        warnings, imported = [], set()
        for statement in statements:
            if isinstance(statement, ImportStatement):
                if statement.module in imported:
                    warnings.append((statement.line, statement.column,
                                     f"Duplicate import of '{statement.module}' (BLZW1004)"))
                imported.add(statement.module)
            declaration = statement.declaration if isinstance(statement, ExportStatement) else statement
            if isinstance(declaration, FunctionDeclaration) and not declaration.body.statements:
                warnings.append((None, None, f"Function '{declaration.name}' has an empty body (BLZW1003)"))
        return warnings
    
    def parse_statement(self):
        """Parse a single statement"""
        token = self.current_token
        
        if not token:
            return None
        
        # Variable declarations
        if token.type == TokenType.VAR:
            return self.parse_variable_declaration(is_constant=False)
        
        if token.type == TokenType.CONSTANT:
            return self.parse_variable_declaration(is_constant=True)

        if token.type == TokenType.BIND:
            return self.parse_bind_declaration()

        # public/private var (and public/private constant) outside of a class
        # body -- e.g. at top level or inside a function/block. Visibility is
        # recorded on the node but only enforced for class fields; elsewhere
        # it behaves exactly like a plain 'var'/'constant'.
        if token.type in (TokenType.PUBLIC, TokenType.PRIVATE, TokenType.PROTECTED):
            saved_position = self.position
            saved_token = self.current_token

            visibility = 'public' if token.type == TokenType.PUBLIC else (
                'private' if token.type == TokenType.PRIVATE else 'protected'
            )
            self.advance()

            if self.current_token and self.current_token.type == TokenType.VAR:
                return self.parse_variable_declaration(
                    is_constant=False, visibility=visibility, had_explicit_modifier=True
                )
            if self.current_token and self.current_token.type == TokenType.CONSTANT:
                return self.parse_variable_declaration(
                    is_constant=True, visibility=visibility, had_explicit_modifier=True
                )

            # Not a variable declaration after all (e.g. this modifier belongs
            # to a class member handled elsewhere) -- restore and fall through.
            self.position = saved_position
            self.current_token = saved_token
        
        # Control flow
        if token.type == TokenType.IF:
            return self.parse_if_statement()
        
        if token.type == TokenType.WHILE:
            return self.parse_while_statement()
        
        if token.type == TokenType.FOR:
            return self.parse_for_statement()
        
        if token.type == TokenType.BREAK:
            self.advance()
            return BreakStatement()
        
        if token.type == TokenType.CONTINUE:
            self.advance()
            return ContinueStatement()
        
        if token.type == TokenType.RETURN:
            return self.parse_return_statement()
        
        # Error handling
        if token.type == TokenType.TRY:
            return self.parse_try_catch_statement()
        
        if token.type == TokenType.THROW:
            return self.parse_throw_statement()
        
        # Custom attributes: 'Define @name' / 'Define @name(...)'
        if token.type == TokenType.DEFINE:
            return self.parse_attribute_definition()

        # Custom attributes attached to a Function/Meta/Class declaration:
        # '@name' / '@name(...)', possibly several stacked in a row.
        if token.type == TokenType.AT:
            attributes = self.parse_attribute_usages()
            return self.parse_attributable_declaration(attributes)

        # Functions and classes
        if token.type == TokenType.META:
            return self.parse_function_declaration(is_meta=True)
        
        if token.type == TokenType.FUNCTION:
            return self.parse_function_declaration(is_meta=False)

        # 'async Function name(...) { ... }' -- 'async' is only meaningful
        # directly in front of a Function declaration; any other use of the
        # keyword falls through to being parsed as a plain identifier/await
        # expression instead of being special-cased here.
        if token.type == TokenType.ASYNC:
            return self.parse_async_function_declaration()
        
        if token.type == TokenType.CLASS:
            return self.parse_class_declaration()

        if token.type == TokenType.STRUCT:
            return self.parse_struct_declaration()

        if token.type == TokenType.ENUM:
            return self.parse_enum_declaration()
        
        # Imports and exports
        if token.type == TokenType.IMPORT:
            return self.parse_import_statement()
        
        if token.type == TokenType.EXPORT:
            return self.parse_export_statement()
        
        # Expression statement or assignment
        expr = self.parse_expression_statement()
        if expr:
            return expr
        
        # Unknown statement, skip token
        self.advance()
        return None
    
    def parse_expression_statement(self):
        """
        Parse an expression that can be:
        - Simple expression: Show("hello")
        - Assignment: x = 5, x += 5
        - Property assignment: this.name = "value" or obj.prop = value
        """
        saved_position = self.position
        saved_token = self.current_token
        
        try:
            expr = self.parse_expression()
            
            # Check if it's an assignment
            if isinstance(expr, PropertyAccess):
                # this.name or obj.prop followed by = or += etc.
                if self.match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN, 
                             TokenType.MINUS_ASSIGN, TokenType.MULTIPLY_ASSIGN, 
                             TokenType.DIVIDE_ASSIGN):
                    operator_token = self.current_token
                    operator = operator_token.value
                    self.advance()
                    value = self.parse_expression()
                    
                    return PropertyAssignment(
                        object=expr.object,
                        property_name=expr.property,
                        value=value,
                        operator=operator
                    )
            
            elif isinstance(expr, Identifier):
                # Simple variable assignment: x = 5, x += 5
                if self.match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN, 
                             TokenType.MINUS_ASSIGN, TokenType.MULTIPLY_ASSIGN, 
                             TokenType.DIVIDE_ASSIGN):
                    operator_token = self.current_token
                    operator = operator_token.value
                    self.advance()
                    value = self.parse_expression()
                    
                    return Assignment(
                        name=expr.name,
                        value=value,
                        operator=operator
                    )
            
            elif isinstance(expr, ArrayAccess):
                # Array element assignment: arr[0] = value
                if self.match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN, 
                             TokenType.MINUS_ASSIGN, TokenType.MULTIPLY_ASSIGN, 
                             TokenType.DIVIDE_ASSIGN):
                    operator_token = self.current_token
                    operator = operator_token.value
                    self.advance()
                    value = self.parse_expression()
                    
                    return ArrayElementAssignment(
                        array=expr.array,
                        index=expr.index,
                        value=value,
                        operator=operator
                    )
            
            # If not an assignment, it's a regular expression statement
            return ExpressionStatement(expression=expr)
            
        except ParserError:
            # Restore position on error
            self.position = saved_position
            self.current_token = saved_token
            return None
    
    def parse_variable_declaration(self, is_constant: bool, visibility: str = 'default',
                                    had_explicit_modifier: bool = False):
        """Parse variable or constant declaration"""
        start_token = self.current_token
        self.advance()  # Skip var/constant keyword

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        value = None
        if self.match(TokenType.ASSIGN):
            self.advance()  # Skip =
            value = self.parse_expression()

        return VariableDeclaration(
            name=name,
            value=value,
            is_constant=is_constant,
            visibility=visibility,
            had_explicit_modifier=had_explicit_modifier,
            line=getattr(start_token, 'line', None),
            column=getattr(start_token, 'column', None),
        )
    
    def parse_bind_declaration(self):
        """Parse a `bind name = expression` declaration.

        Deliberately kept separate from parse_variable_declaration (rather
        than bolting a `is_bind` flag onto VariableDeclaration) so `var`,
        `constant`, and `bind` stay three clearly distinct AST shapes, per
        the language design -- but it reuses the exact same expression
        parsing, so a Bind's initializer supports everything a `var`
        initializer does (literals, lists, objects, calls, ...).
        """
        start_token = self.current_token
        self.advance()  # Skip 'bind' keyword

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        value = None
        if self.match(TokenType.ASSIGN):
            self.advance()  # Skip =
            value = self.parse_expression()

        return BindDeclaration(
            name=name,
            value=value,
            line=getattr(start_token, 'line', None),
            column=getattr(start_token, 'column', None),
        )

    def parse_block(self) -> BlockStatement:
        """Parse a block of statements enclosed in braces"""
        self.expect(TokenType.LBRACE)
        
        statements = []
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            if self.current_token.type == TokenType.EOF:
                raise ParserError(
                    "Unterminated block, expected '}'",
                    self.current_token.line,
                    self.current_token.column
                )
            statement = self.parse_statement()
            if statement:
                statements.append(statement)
        
        self.expect(TokenType.RBRACE)
        return BlockStatement(statements=statements)
    
    def parse_if_statement(self):
        """Parse if/else if/else statement"""
        self.advance()  # Skip if
        
        condition = self.parse_expression()
        then_branch = self.parse_block()
        
        else_if_branches = []
        else_branch = None
        
        while self.match(TokenType.ELSE):
            self.advance()  # Skip else
            
            if self.match(TokenType.IF):
                self.advance()  # Skip if
                elif_condition = self.parse_expression()
                elif_body = self.parse_block()
                else_if_branches.append((elif_condition, elif_body))
            else:
                else_branch = self.parse_block()
                break
        
        return IfStatement(
            condition=condition,
            then_branch=then_branch,
            else_if_branches=else_if_branches,
            else_branch=else_branch
        )
    
    def parse_while_statement(self):
        """Parse while loop"""
        self.advance()  # Skip while
        
        condition = self.parse_expression()
        body = self.parse_block()
        
        return WhileStatement(condition=condition, body=body)
    
    def parse_for_statement(self):
        """Parse for or for-each loop"""
        self.advance()  # Skip for
        
        var_token = self.expect(TokenType.IDENTIFIER)
        var_name = var_token.value
        
        self.expect(TokenType.IN)
        
        iterable = self.parse_expression()
        body = self.parse_block()
        
        return ForStatement(variable=var_name, iterable=iterable, body=body)
    
    def parse_return_statement(self):
        """Parse return statement"""
        self.advance()  # Skip return
        
        value = None
        # Check if there is a return value (not at end of block)
        if self.current_token and self.current_token.type not in [
            TokenType.RBRACE, TokenType.EOF, TokenType.CATCH, TokenType.FINALLY
        ]:
            value = self.parse_expression()
        
        return ReturnStatement(value=value)
    
    def parse_throw_statement(self):
        """Parse throw statement"""
        self.advance()  # Skip throw
        
        value = self.parse_expression()
        return ThrowStatement(value=value)
    
    def parse_try_catch_statement(self):
        """Parse try/catch/finally statement"""
        self.advance()  # Skip try
        
        try_block = self.parse_block()
        
        self.expect(TokenType.CATCH)
        self.expect(TokenType.LPAREN)
        error_var_token = self.expect(TokenType.IDENTIFIER)
        error_var = error_var_token.value
        self.expect(TokenType.RPAREN)
        
        catch_block = self.parse_block()
        
        finally_block = None
        if self.match(TokenType.FINALLY):
            self.advance()  # Skip finally
            finally_block = self.parse_block()
        
        return TryCatchStatement(
            try_block=try_block,
            catch_block=catch_block,
            error_var=error_var,
            finally_block=finally_block
        )
    
    # =====================
    # Custom Attributes
    # =====================

    def parse_attribute_definition(self):
        """Parse 'Define @name' or 'Define @name(param, ...)'.

        This only registers the attribute's name and parameter list so it
        can later be attached with '@name' / '@name(args)' -- it does not
        execute or attach anything itself.
        """
        start_token = self.current_token
        self.advance()  # Skip Define

        if not self.match(TokenType.AT):
            found = self.current_token.type.name if self.current_token else 'EOF'
            raise InvalidAttributeSyntaxError(
                f"expected '@' after 'Define', but found {found}",
                start_token.line, start_token.column, self.filename,
            )
        self.advance()  # Skip @

        if not self.match(TokenType.IDENTIFIER):
            found = self.current_token.type.name if self.current_token else 'EOF'
            raise InvalidAttributeSyntaxError(
                f"expected an attribute name after '@', but found {found}",
                start_token.line, start_token.column, self.filename,
            )
        name_token = self.current_token
        name = name_token.value
        self.advance()

        parameters = []
        if self.match(TokenType.LPAREN):
            self.advance()  # Skip (
            if not self.match(TokenType.RPAREN):
                param_token = self.expect(TokenType.IDENTIFIER)
                parameters.append(param_token.value)
                while self.match(TokenType.COMMA):
                    self.advance()  # Skip comma
                    param_token = self.expect(TokenType.IDENTIFIER)
                    parameters.append(param_token.value)
            self.expect(TokenType.RPAREN)

        if name in self.defined_attributes:
            raise DuplicateAttributeDefinitionError(name, name_token.line, name_token.column, self.filename)

        self.defined_attributes[name] = parameters

        return self._tag(AttributeDefinition(name=name, parameters=parameters), start_token)

    def parse_attribute_usages(self):
        """Parse one or more consecutive '@name' / '@name(args)' usages
        immediately preceding a Function/Meta/Class declaration. Returns a
        list of AttributeUsage nodes (arguments left unevaluated -- they're
        evaluated at runtime like any other expression)."""
        usages = []
        seen = set()

        while self.match(TokenType.AT):
            at_token = self.current_token
            self.advance()  # Skip @

            if not self.match(TokenType.IDENTIFIER):
                found = self.current_token.type.name if self.current_token else 'EOF'
                raise InvalidAttributeSyntaxError(
                    f"expected an attribute name after '@', but found {found}",
                    at_token.line, at_token.column, self.filename,
                )
            name_token = self.current_token
            name = name_token.value
            self.advance()

            if name not in self.defined_attributes:
                raise UndefinedAttributeError(
                    name, name_token.line, name_token.column, self.filename,
                    known_names=list(self.defined_attributes.keys()),
                )

            arguments = []
            if self.match(TokenType.LPAREN):
                self.advance()  # Skip (
                if not self.match(TokenType.RPAREN):
                    arguments.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        self.advance()  # Skip comma
                        if self.match(TokenType.RPAREN):
                            break  # Allow trailing comma
                        arguments.append(self.parse_expression())
                self.expect(TokenType.RPAREN)

            expected_params = self.defined_attributes[name]
            if len(arguments) != len(expected_params):
                raise InvalidAttributeArgumentsError(
                    name, len(expected_params), len(arguments),
                    name_token.line, name_token.column, self.filename,
                )

            if name in seen:
                raise DuplicateAttributeUsageError(name, name_token.line, name_token.column, self.filename)
            seen.add(name)

            usages.append(self._tag(AttributeUsage(name=name, arguments=arguments), name_token))

        return usages

    def parse_attributable_declaration(self, attributes):
        """Parse the Function/Meta/Class declaration that a stack of
        '@name' attributes was written above, and attach them to it."""
        token = self.current_token
        if token is None or token.type not in (TokenType.META, TokenType.FUNCTION, TokenType.CLASS):
            found = token.type.name if token else 'EOF'
            raise AttributeTargetError(
                f"'{found}' (attributes may only be applied to a Function, Meta, or Class declaration)",
                attributes[0].line if attributes else None,
                attributes[0].column if attributes else None,
                self.filename,
            )

        if token.type == TokenType.META:
            declaration = self.parse_function_declaration(is_meta=True)
        elif token.type == TokenType.FUNCTION:
            declaration = self.parse_function_declaration(is_meta=False)
        else:
            declaration = self.parse_class_declaration()

        declaration.attributes = attributes
        return declaration

    def parse_async_function_declaration(self):
        """Parse 'async Function name(...) { ... }'.

        'async' is only valid directly in front of a Function declaration
        (not 'Meta', which is a constructor and never called/awaited like a
        regular function). Kept as a thin wrapper around
        parse_function_declaration rather than duplicating its body, so
        parameter/body parsing stays identical between sync and async
        functions.
        """
        async_token = self.current_token
        self.advance()  # Skip 'async'

        if not self.match(TokenType.FUNCTION):
            found = self.current_token.type.name if self.current_token else 'EOF'
            raise ParserError(
                f"Expected 'Function' after 'async', but found {found}",
                async_token.line, async_token.column
            )

        return self.parse_function_declaration(is_meta=False, is_async=True)

    def parse_function_declaration(self, is_meta: bool, is_async: bool = False):
        """Parse Meta or Function declaration"""
        self.advance()  # Skip Meta/Function
        
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        
        self.expect(TokenType.LPAREN)
        
        parameters = []
        if not self.match(TokenType.RPAREN):
            param_token = self.expect(TokenType.IDENTIFIER)
            parameters.append(param_token.value)
            
            while self.match(TokenType.COMMA):
                self.advance()  # Skip comma
                param_token = self.expect(TokenType.IDENTIFIER)
                parameters.append(param_token.value)
        
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        
        declaration = FunctionDeclaration(
            name=name,
            parameters=parameters,
            body=body,
            is_meta=is_meta
        )
        # Set dynamically rather than as a constructor kwarg: FunctionDeclaration
        # predates 'async', so this keeps every existing call site (and any
        # other code that builds a FunctionDeclaration without knowing about
        # 'async') working unchanged, while still exposing node.is_async to
        # the interpreter for every function -- sync functions simply read
        # back the default False set here.
        declaration.is_async = is_async
        return declaration
    
    def parse_class_declaration(self):
        """Parse Class declaration"""
        self.advance()  # Skip Class
        
        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value
        
        # Handle inheritance
        parent_class = None
        if self.match(TokenType.COLON):
            self.advance()  # Skip :
            parent_token = self.expect(TokenType.IDENTIFIER)
            parent_class = parent_token.value
        
        self.expect(TokenType.LBRACE)
        
        members = []
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            # Custom attributes attached directly to a class member, e.g.
            # '@logged' above 'Function Create(...)'.
            member_attributes = []
            if self.current_token.type == TokenType.AT:
                member_attributes = self.parse_attribute_usages()

            if self.current_token is None:
                break

            if self.current_token.type == TokenType.CONSTRUCTOR:
                if member_attributes:
                    raise AttributeTargetError(
                        "a Constructor", member_attributes[0].line, member_attributes[0].column, self.filename,
                    )
                members.append(self.parse_constructor())
                continue

            # Collect any combination/order of modifiers: static, public,
            # private, protected (e.g. "public static Function", "static
            # private Function", or just "private Function").
            is_static = False
            access_modifier = 'public'
            saw_modifier = False
            while self.current_token and self.current_token.type in (
                TokenType.STATIC, TokenType.PUBLIC,
                TokenType.PRIVATE, TokenType.PROTECTED
            ):
                saw_modifier = True
                if self.current_token.type == TokenType.STATIC:
                    is_static = True
                elif self.current_token.type == TokenType.PUBLIC:
                    access_modifier = 'public'
                elif self.current_token.type == TokenType.PRIVATE:
                    access_modifier = 'private'
                elif self.current_token.type == TokenType.PROTECTED:
                    access_modifier = 'protected'
                self.advance()

            if self.current_token is None:
                break

            if self.current_token.type == TokenType.META:
                func = self.parse_function_declaration(is_meta=True)
                # A small, explicit hook vocabulary avoids changing the
                # long-standing meaning of ordinary class Meta methods.
                if func.name in ('OnCall', 'Before', 'OnReturn', 'After', 'OnError'):
                    if member_attributes:
                        raise AttributeTargetError(
                            "a Meta lifecycle hook", member_attributes[0].line,
                            member_attributes[0].column, self.filename,
                        )
                    members.append(MetaHookDeclaration(
                        hook_name=func.name,
                        parameters=func.parameters,
                        body=func.body,
                    ))
                    continue
                func.is_static = is_static
                func.access_modifier = access_modifier
                func.had_explicit_modifier = saw_modifier
                func.attributes = member_attributes
                members.append(func)
            elif self.current_token.type == TokenType.FUNCTION:
                func = self.parse_function_declaration(is_meta=False)
                func.is_static = is_static
                func.access_modifier = access_modifier
                func.had_explicit_modifier = saw_modifier
                func.attributes = member_attributes
                members.append(func)
            elif self.current_token.type == TokenType.VAR:
                if member_attributes:
                    raise AttributeTargetError(
                        "a 'var' field", member_attributes[0].line, member_attributes[0].column, self.filename,
                    )
                field = self.parse_variable_declaration(
                    is_constant=False,
                    visibility=access_modifier if saw_modifier else 'default',
                    had_explicit_modifier=saw_modifier,
                )
                field.is_static = is_static
                members.append(field)
            elif self.current_token.type == TokenType.CONSTANT:
                if member_attributes:
                    raise AttributeTargetError(
                        "a 'constant' field", member_attributes[0].line, member_attributes[0].column, self.filename,
                    )
                field = self.parse_variable_declaration(
                    is_constant=True,
                    visibility=access_modifier if saw_modifier else 'default',
                    had_explicit_modifier=saw_modifier,
                )
                field.is_static = is_static
                members.append(field)
            elif member_attributes:
                # Attributes were consumed but nothing valid followed them.
                raise AttributeTargetError(
                    "this class member", member_attributes[0].line, member_attributes[0].column, self.filename,
                )
            elif saw_modifier:
                # Modifiers were consumed but nothing valid followed them
                # (e.g. "public" applied to something unsupported) - skip
                # the unexpected token rather than looping forever.
                self.advance()
            else:
                # Unknown member, skip token
                self.advance()
        
        self.expect(TokenType.RBRACE)
        
        return ClassDeclaration(
            name=name, 
            members=members,
            parent_class=parent_class
        )
    
    def parse_constructor(self):
        """Parse Constructor declaration"""
        self.advance()  # Skip Constructor
        
        self.expect(TokenType.LPAREN)
        
        parameters = []
        if not self.match(TokenType.RPAREN):
            param_token = self.expect(TokenType.IDENTIFIER)
            parameters.append(param_token.value)
            
            while self.match(TokenType.COMMA):
                self.advance()
                param_token = self.expect(TokenType.IDENTIFIER)
                parameters.append(param_token.value)
        
        self.expect(TokenType.RPAREN)
        body = self.parse_block()
        
        return ConstructorDeclaration(parameters=parameters, body=body)
    
    def parse_struct_declaration(self):
        """Parse a Struct declaration.

        Struct is an independent, data-only language feature -- it does not
        support inheritance, constructors, methods, or visibility modifiers.
        A Struct body contains a flat list of fields, one per line, each
        either bare (`name`, defaults to null) or with a default value
        expression (`age = 18`). Any of those unsupported constructs inside
        the body produces a dedicated error immediately rather than being
        silently coerced into a field.
        """
        start_token = self.current_token
        self.advance()  # Skip Struct

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        # Struct never supports inheritance -- reject `Struct Foo : Bar {...}`
        # immediately instead of silently ignoring the parent reference.
        if self.match(TokenType.COLON):
            colon_token = self.current_token
            raise StructInheritanceError(
                f"Struct '{name}' cannot use ':' to inherit from another type",
                colon_token.line, colon_token.column, self.filename,
            )

        self.expect(TokenType.LBRACE)

        fields = []
        seen_fields = set()
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            token = self.current_token

            if token.type == TokenType.EOF:
                raise ParserError(
                    "Unterminated Struct body, expected '}'",
                    token.line, token.column,
                )

            if token.type in (TokenType.FUNCTION, TokenType.META):
                raise StructMethodNotAllowedError(name, token.line, token.column, self.filename)

            if token.type == TokenType.CONSTRUCTOR:
                raise StructConstructorNotAllowedError(name, token.line, token.column, self.filename)

            if token.type in (TokenType.PUBLIC, TokenType.PRIVATE, TokenType.PROTECTED, TokenType.STATIC):
                raise InvalidStructFieldError(
                    f"modifier '{token.value}' is not allowed in Struct '{name}' -- "
                    "Struct fields do not support visibility or static modifiers",
                    token.line, token.column, self.filename,
                )

            if token.type != TokenType.IDENTIFIER:
                raise InvalidStructFieldError(
                    f"unexpected token '{token.value}' in Struct '{name}'",
                    token.line, token.column, self.filename,
                )

            field_token = token
            field_name = token.value
            self.advance()  # Skip field name

            default_value = None
            if self.match(TokenType.ASSIGN):
                self.advance()  # Skip =
                default_value = self.parse_expression()

            if field_name in seen_fields:
                raise DuplicateStructFieldError(name, field_name, field_token.line, field_token.column, self.filename)
            seen_fields.add(field_name)

            fields.append(self._tag(
                StructField(name=field_name, default_value=default_value), field_token
            ))

        self.expect(TokenType.RBRACE)

        return self._tag(StructDeclaration(name=name, fields=fields), start_token)

    def parse_enum_declaration(self):
        """Parse an Enum declaration.

        Enum is an independent, data-only language feature, like Struct: no
        inheritance, methods, or constructors. A body is a flat list of bare
        identifiers, one per line, each optionally followed by an explicit
        `= <int|string literal>` value. Members with no explicit value
        auto-increment from the previous numeric value, starting at 0.
        """
        start_token = self.current_token
        self.advance()  # Skip Enum

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        self.expect(TokenType.LBRACE)

        members = []
        seen_members = set()
        while self.current_token and self.current_token.type != TokenType.RBRACE:
            token = self.current_token

            if token.type == TokenType.EOF:
                raise ParserError(
                    "Unterminated Enum body, expected '}'",
                    token.line, token.column,
                )

            if token.type != TokenType.IDENTIFIER:
                raise InvalidEnumMemberError(
                    f"unexpected token '{token.value}' in Enum '{name}'",
                    token.line, token.column, self.filename,
                )

            member_token = token
            member_name = token.value
            self.advance()  # Skip member name

            value = None
            if self.match(TokenType.ASSIGN):
                self.advance()  # Skip =
                value_token = self.current_token
                if value_token is None or value_token.type not in (TokenType.INTEGER, TokenType.STRING):
                    raise InvalidEnumValueError(
                        name, member_name,
                        value_token.line if value_token else member_token.line,
                        value_token.column if value_token else member_token.column,
                        self.filename,
                    )
                value = self.parse_expression()

            if member_name in seen_members:
                raise DuplicateEnumMemberError(name, member_name, member_token.line, member_token.column, self.filename)
            seen_members.add(member_name)

            members.append(self._tag(EnumMember(name=member_name, value=value), member_token))

        self.expect(TokenType.RBRACE)

        return self._tag(EnumDeclaration(name=name, members=members), start_token)

    def parse_import_statement(self):
        """Parse named, namespace, default, and legacy imports."""
        import_token = self.current_token
        self.advance()  # Skip Import
        bindings, namespace, default_name, alias = [], None, None, None
        if self.match(TokenType.LBRACE):
            self.advance()
            while not self.match(TokenType.RBRACE):
                exported = self.expect(TokenType.IDENTIFIER).value
                local = exported
                if self.match(TokenType.AS):
                    self.advance()
                    local = self.expect(TokenType.IDENTIFIER).value
                bindings.append((exported, local))
                if not self.match(TokenType.COMMA):
                    break
                self.advance()
            self.expect(TokenType.RBRACE)
            self.expect(TokenType.FROM)
            module = self.expect(TokenType.STRING).value
        elif self.match(TokenType.MULTIPLY):
            self.advance()
            self.expect(TokenType.AS)
            namespace = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.FROM)
            module = self.expect(TokenType.STRING).value
        elif self.match(TokenType.IDENTIFIER):
            name = self.current_token.value
            self.advance()
            if self.match(TokenType.FROM):
                self.advance()
                default_name = name
                module = self.expect(TokenType.STRING).value
            else:
                module = name
                if self.match(TokenType.AS):
                    self.advance()
                    alias = self.expect(TokenType.IDENTIFIER).value
        elif self.match(TokenType.STRING):
            module = self.current_token.value
            self.advance()
            if self.match(TokenType.AS):
                self.advance()
                alias = self.expect(TokenType.IDENTIFIER).value
        else:
            raise ParserError("Expected an import target", self.current_token.line, self.current_token.column)
        return ImportStatement(module=module, bindings=bindings, namespace=namespace,
                               default_name=default_name, alias=alias,
                               line=import_token.line, column=import_token.column)
    
    def parse_export_statement(self):
        """Parse an exported declaration or ``export default <expression>``."""
        self.advance()  # Skip Export
        is_default = self.match(TokenType.DEFAULT)
        if is_default:
            self.advance()
        if self.match(TokenType.VAR):
            declaration = self.parse_variable_declaration(False)
        elif self.match(TokenType.CONSTANT):
            declaration = self.parse_variable_declaration(True)
        elif self.match(TokenType.META):
            declaration = self.parse_function_declaration(True)
        elif self.match(TokenType.FUNCTION):
            declaration = self.parse_function_declaration(False)
        elif self.match(TokenType.CLASS):
            declaration = self.parse_class_declaration()
        elif self.match(TokenType.ENUM):
            declaration = self.parse_enum_declaration()
        elif self.match(TokenType.STRUCT):
            declaration = self.parse_struct_declaration()
        elif is_default:
            # A default export is a value, not necessarily a declaration.
            # This permits `export default greet` and object/class factory APIs.
            return ExportStatement(value=self.parse_expression(), is_default=True)
        else:
            raise ParserError("Export must be followed by a declaration, or be `export default <expression>`",
                              self.current_token.line, self.current_token.column)
        return ExportStatement(declaration=declaration, is_default=is_default)
    
    # =====================
    # Expression Parsing
    # =====================
    
    def parse_single_expression(self):
        """Public entry point for parsing a *single, complete* expression
        out of a token stream with nothing else around it -- what `eval()`
        uses to turn a source string into an expression AST.

        Unlike the internal `parse_expression()` (the operator-precedence
        entry point used everywhere inside statement/expression grammar,
        which happily stops as soon as it has a valid expression and lets
        its caller decide what comes next), this method requires there be
        *nothing* left except EOF afterward -- so `eval("10 + 20 garbage")`
        is a real ParserError instead of silently discarding "garbage".
        """
        try:
            if self.current_token is None or self.current_token.type == TokenType.EOF:
                raise ParserError("eval() requires a non-empty expression")

            expr = self.parse_expression()

            if self.current_token is not None and self.current_token.type != TokenType.EOF:
                raise ParserError(
                    f"Unexpected token after expression: {self.current_token.type.name} "
                    f"(eval() accepts exactly one expression, with no trailing tokens)",
                    self.current_token.line, self.current_token.column, self.current_token.filename
                )

            return expr
        except ParserError as error:
            # Mirrors parse()'s enrichment so an eval() ParserError gets the
            # same filename/line/column completion a top-level parse error does.
            if not error.filename:
                token = self.current_token
                error.filename = self.filename
                error.line = error.line or (token.line if token else None)
                error.column = error.column or (token.column if token else None)
                error.args = (error.format_error(),)
            raise

    def parse_expression(self):
        """Parse an expression starting from lowest precedence"""
        return self.parse_logical_or()
    
    def parse_logical_or(self):
        """Parse logical OR operations (lowest precedence)"""
        left = self.parse_logical_and()
        
        while self.match(TokenType.OR):
            operator_token = self.current_token
            self.advance()
            right = self.parse_logical_and()
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_logical_and(self):
        """Parse logical AND operations"""
        left = self.parse_comparison()
        
        while self.match(TokenType.AND):
            operator_token = self.current_token
            self.advance()
            right = self.parse_comparison()
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_comparison(self):
        """Parse comparison operations (==, !=, <, >, <=, >=)"""
        left = self.parse_addition()
        
        while self.match(
            TokenType.EQUALS, TokenType.NOT_EQUALS,
            TokenType.LESS, TokenType.GREATER,
            TokenType.LESS_EQUALS, TokenType.GREATER_EQUALS
        ):
            operator_token = self.current_token
            self.advance()
            right = self.parse_addition()
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_addition(self):
        """Parse addition and subtraction"""
        left = self.parse_multiplication()
        
        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator_token = self.current_token
            self.advance()
            right = self.parse_multiplication()
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_multiplication(self):
        """Parse multiplication, division, and modulo"""
        left = self.parse_power()
        
        while self.match(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            operator_token = self.current_token
            self.advance()
            right = self.parse_power()
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_power(self):
        """Parse exponentiation (^ or **). Higher precedence than * / %,
        and right-associative, so 2 ^ 3 ^ 2 == 2 ^ (3 ^ 2)."""
        left = self.parse_unary()
        
        if self.match(TokenType.POWER):
            operator_token = self.current_token
            self.advance()
            right = self.parse_power()  # right-recursion => right-associative
            left = self._binary(left, operator_token.value, right, operator_token)
        
        return left
    
    def parse_unary(self):
        """Parse unary operations (-, not, await)"""
        if self.match(TokenType.MINUS, TokenType.NOT):
            operator_token = self.current_token
            self.advance()
            operand = self.parse_unary()
            return self._tag(UnaryOperation(
                operator=operator_token.value,
                operand=operand
            ), operator_token)

        # 'await' binds like a unary prefix operator so it composes with
        # everything else at this precedence tier -- 'await Foo()',
        # 'return await Foo()', and 'return 2 * await Foo()' (where the
        # '*' is handled by parse_multiplication, one level up, and simply
        # sees the whole await expression as its right operand) all fall
        # out of this placement for free, with no separate grammar rule
        # needed per call site.
        if self.match(TokenType.AWAIT):
            await_token = self.current_token
            self.advance()
            operand = self.parse_unary()
            return self._tag(AwaitExpression(value=operand), await_token)
        
        return self.parse_primary()
    
    def parse_primary(self):
        """Parse primary expressions with chained access"""
        expr = self.parse_atom()
        
        # Handle chained operations: property access, array access, function calls
        while True:
            # Property access: expr.property
            if self.match(TokenType.DOT):
                self.advance()  # Skip dot
                prop_token = self.expect(TokenType.IDENTIFIER)
                expr = PropertyAccess(object=expr, property=prop_token.value)
            
            # Array access: expr[index]
            elif self.match(TokenType.LBRACKET):
                self.advance()  # Skip [
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = ArrayAccess(array=expr, index=index)
            
            # Function call: expr(args)
            elif self.match(TokenType.LPAREN):
                call_token = self.current_token
                self.advance()  # Skip (
                
                arguments = []
                if not self.match(TokenType.RPAREN):
                    arguments.append(self.parse_call_argument())
                    
                    while self.match(TokenType.COMMA):
                        self.advance()  # Skip comma
                        arguments.append(self.parse_call_argument())
                
                self.expect(TokenType.RPAREN)
                expr = self._tag(FunctionCall(callee=expr, arguments=arguments), call_token)
            
            else:
                break
        
        return expr
    
    def parse_call_argument(self):
        """Parse a single call argument: either a plain expression (positional)
        or `name: expression` (named). Named arguments are integrated into
        the general call-argument parser -- shared by every call site --
        rather than through a second, incompatible argument parser, so
        Struct construction and any future named-argument use reuse the same
        grammar. `identifier ':'` is unambiguous here: BlazeLang has no
        ternary or slice syntax that could also start with that pattern in
        argument position, and object literals are only entered via a
        leading '{'.
        """
        if (self.current_token and self.current_token.type == TokenType.IDENTIFIER
                and self.peek() is not None and self.peek().type == TokenType.COLON):
            name_token = self.current_token
            self.advance()  # Skip identifier
            self.advance()  # Skip :
            value = self.parse_expression()
            return self._tag(NamedArgument(name=name_token.value, value=value), name_token)

        return self.parse_expression()

    def parse_atom(self):
        """Parse atomic expressions (literals, identifiers, parenthesized expressions)"""
        token = self.current_token
        
        if not token:
            return None
        
        # Number literals.
        # IMPORTANT: INTEGER tokens must keep a Python `int` value (not be
        # forced to `float`) so the interpreter can tell `1` (Integer) apart
        # from `1.0` (Float) later -- see builtin_type() in interpreter.py,
        # which distinguishes the two by Python type, not by numeric value.
        # Forcing every literal to float here was the root cause of
        # `type(1.0)`/`type(2.5)` reporting the wrong type: both an integer
        # and a float literal became indistinguishable Python floats.
        if token.type == TokenType.INTEGER:
            self.advance()
            return self._tag(NumberLiteral(value=token.value), token)
        
        if token.type == TokenType.FLOAT:
            self.advance()
            return self._tag(NumberLiteral(value=token.value), token)
        
        # String literals
        if token.type == TokenType.STRING:
            self.advance()
            return self._tag(StringLiteral(value=token.value), token)
        
        # Boolean and null literals
        if token.type == TokenType.BOOLEAN:
            self.advance()
            return self._tag(BooleanLiteral(value=token.value), token)
        
        if token.type == TokenType.NULL:
            self.advance()
            return self._tag(NullLiteral(), token)
        
        # this and super
        if token.type == TokenType.THIS:
            self.advance()
            return self._tag(ThisExpression(), token)
        
        if token.type == TokenType.SUPER:
            self.advance()
            return self._tag(SuperExpression(), token)
        
        # Identifiers
        if token.type == TokenType.IDENTIFIER:
            name = token.value
            self.advance()
            return self._tag(Identifier(name=name), token)
        
        # Reflect <operation>(...) construct
        if token.type == TokenType.REFLECT:
            return self.parse_reflect_userdata()

        # Array literals
        if token.type == TokenType.LBRACKET:
            return self.parse_array_literal()
        
        # Object literals
        if token.type == TokenType.LBRACE:
            return self.parse_object_literal()

        # Anonymous functions are values: `{ handler: function() { ... } }`.
        if token.type == TokenType.FUNCTION:
            return self.parse_function_expression()
        
        # Parenthesized expressions
        if token.type == TokenType.LPAREN:
            self.advance()  # Skip (
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr
        
        # End of block or file
        if token.type in [TokenType.RBRACE, TokenType.RBRACKET, TokenType.EOF]:
            return None
        
        raise ParserError(
            f"Unexpected token {token.type.name}",
            token.line,
            token.column
        )

    def parse_function_expression(self):
        """Parse a function literal (the value form has no name)."""
        start_token = self.current_token
        self.advance()
        self.expect(TokenType.LPAREN)
        parameters = []
        if not self.match(TokenType.RPAREN):
            parameters.append(self.expect(TokenType.IDENTIFIER).value)
            while self.match(TokenType.COMMA):
                self.advance()
                parameters.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.RPAREN)
        return self._tag(FunctionExpression(parameters=parameters, body=self.parse_block()), start_token)
    
    # =====================
    # Reflect Userdata
    # =====================

    def parse_reflect_userdata(self):
        """Parse `Reflect <operation>( <source-expr> { accept{...} expect{...} reject{...} } )`.

        The operation name (`userdata`, `project`, `data`, `api`, or any
        other identifier) is read generically as an IDENTIFIER -- it is
        never matched against a fixed keyword -- and stored on the
        resulting node so any name works without the parser hardcoding it.

        This is deliberately its own grammar rule rather than a normal
        function call: the trailing `{ accept {...} expect {...} reject
        {...} }` block is not an object literal (its entries are bare
        `name { ... }` / `name` field specs, not `key: value` pairs), so it
        can't be reused through parse_object_literal/parse_call_argument.
        """
        start_token = self.current_token
        self.advance()  # Skip 'Reflect'

        operation_token = self.expect(TokenType.IDENTIFIER)
        operation_name = operation_token.value

        self.expect(TokenType.LPAREN)

        source_expr = self.parse_expression()

        accept_spec = None
        expect_spec = None
        reject_spec = None

        if self.match(TokenType.LBRACE):
            self.advance()  # Skip {

            while not self.match(TokenType.RBRACE):
                if self.current_token is None or self.current_token.type == TokenType.EOF:
                    raise ParserError(
                        f"Unterminated 'Reflect {operation_name}' options block, expected '}}'",
                        start_token.line, start_token.column, start_token.filename
                    )

                section_token = self.current_token

                if section_token.type == TokenType.ACCEPT:
                    self.advance()
                    if accept_spec is not None:
                        raise ParserError(
                            f"Duplicate 'accept' block inside 'Reflect {operation_name}'",
                            section_token.line, section_token.column, section_token.filename
                        )
                    accept_spec = self.parse_reflect_field_block()
                elif section_token.type == TokenType.EXPECT:
                    self.advance()
                    if expect_spec is not None:
                        raise ParserError(
                            f"Duplicate 'expect' block inside 'Reflect {operation_name}'",
                            section_token.line, section_token.column, section_token.filename
                        )
                    expect_spec = self.parse_reflect_field_block()
                elif section_token.type == TokenType.REJECT:
                    self.advance()
                    if reject_spec is not None:
                        raise ParserError(
                            f"Duplicate 'reject' block inside 'Reflect {operation_name}'",
                            section_token.line, section_token.column, section_token.filename
                        )
                    reject_spec = self.parse_reflect_field_block()
                else:
                    raise ParserError(
                        f"Expected 'accept', 'expect', or 'reject' inside 'Reflect {operation_name}' options, "
                        f"but found {section_token.type.name}",
                        section_token.line, section_token.column, section_token.filename
                    )

            self.expect(TokenType.RBRACE)

        self.expect(TokenType.RPAREN)

        return self._tag(ReflectUserdata(
            operation=operation_name,
            source=source_expr,
            accept=accept_spec,
            expect=expect_spec,
            reject=reject_spec,
        ), start_token)

    def parse_reflect_field_block(self) -> 'ReflectFieldSpec':
        """Parse a `{ field field2 { nested } ... }` field-spec block used by
        `accept`/`expect`/`reject`. Fields may be separated by newlines
        (already discarded by the lexer) or an optional comma, and a field
        may itself carry a nested block to describe a nested object/array
        of objects.
        """
        open_token = self.current_token
        self.expect(TokenType.LBRACE)

        fields = {}

        while not self.match(TokenType.RBRACE):
            if self.current_token is None or self.current_token.type == TokenType.EOF:
                raise ParserError(
                    "Unterminated field block, expected '}'",
                    open_token.line, open_token.column, open_token.filename
                )

            name_token = self.expect(TokenType.IDENTIFIER)

            nested_spec = None
            if self.match(TokenType.LBRACE):
                nested_spec = self.parse_reflect_field_block()

            fields[name_token.value] = nested_spec

            if self.match(TokenType.COMMA):
                self.advance()

        self.expect(TokenType.RBRACE)
        return ReflectFieldSpec(fields=fields)

    def parse_array_literal(self):
        """Parse array literal"""
        self.advance()  # Skip [
        
        elements = []
        if not self.match(TokenType.RBRACKET):
            elements.append(self.parse_expression())
            
            while self.match(TokenType.COMMA):
                self.advance()  # Skip comma
                if self.match(TokenType.RBRACKET):
                    break  # Allow trailing comma
                elements.append(self.parse_expression())
        
        self.expect(TokenType.RBRACKET)
        return ArrayLiteral(elements=elements)
    
    def _expect_object_literal_key(self):
        """Expect an object-literal key token: either IDENTIFIER (`name:`)
        or STRING (`"name":`). Kept separate from the general-purpose
        `expect()` (which only matches a single token type) so no existing
        call site is affected."""
        if self.current_token and self.current_token.type in (TokenType.IDENTIFIER, TokenType.STRING):
            token = self.current_token
            self.advance()
            return token

        found = self.current_token.type.name if self.current_token else 'EOF'
        line = self.current_token.line if self.current_token else 0
        col = self.current_token.column if self.current_token else 0

        raise ParserError(
            f"Expected an object key (identifier or string), but found {found}",
            line, col
        )

    def parse_object_literal(self):
        """Parse object literal.

        Keys may be a bare IDENTIFIER (`name: "BlazeLang"`) or a STRING
        literal (`"name": "BlazeLang"`) -- both forms produce the exact same
        string key internally (`"name"`), so `obj.name` and `obj["name"]`
        always resolve to whatever was written under either spelling.
        Quoted keys are what let you use a key that isn't a valid
        identifier, e.g. `"api-key"` or a reserved word like `"if"`.
        """
        self.advance()  # Skip {

        properties = {}
        if not self.match(TokenType.RBRACE):
            key_token = self._expect_object_literal_key()
            self.expect(TokenType.COLON)
            value = self.parse_expression()
            properties[key_token.value] = value

            while self.match(TokenType.COMMA):
                self.advance()  # Skip comma
                if self.match(TokenType.RBRACE):
                    break  # Allow trailing comma
                key_token = self._expect_object_literal_key()
                self.expect(TokenType.COLON)
                value = self.parse_expression()
                properties[key_token.value] = value

        self.expect(TokenType.RBRACE)
        return ObjectLiteral(properties=properties)
