"""
Token types and Token class for BlazeLang
Defines all possible token types in the language
"""

from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    """All possible token types in BlazeLang"""
    
    # Literals
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    BOOLEAN = auto()
    NULL = auto()
    
    # Identifiers
    IDENTIFIER = auto()
    
    # Keywords
    VAR = auto()
    CONSTANT = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    META = auto()
    FUNCTION = auto()
    CLASS = auto()
    STRUCT = auto()
    CONSTRUCTOR = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    IMPORT = auto()
    EXPORT = auto()
    FROM = auto()
    AS = auto()
    DEFAULT = auto()
    TRY = auto()
    CATCH = auto()
    FINALLY = auto()
    THROW = auto()
    STATIC = auto()
    ASYNC = auto()
    AWAIT = auto()
    PUBLIC = auto()
    PRIVATE = auto()
    PROTECTED = auto()
    OVERRIDE = auto()
    THIS = auto()
    SUPER = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    
    # Arithmetic Operators
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    POWER = auto()
    
    # Assignment Operators
    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    MULTIPLY_ASSIGN = auto()
    DIVIDE_ASSIGN = auto()
    
    # Comparison Operators
    EQUALS = auto()
    NOT_EQUALS = auto()
    GREATER = auto()
    LESS = auto()
    GREATER_EQUALS = auto()
    LESS_EQUALS = auto()
    
    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    SEMICOLON = auto()
    ARROW = auto()
    
    # Special
    EOF = auto()
    NEWLINE = auto()


class Token:
    """Represents a single token in the source code"""
    
    def __init__(self, token_type: TokenType, value: Any, line: int, column: int, filename: str = "<unknown>"):
        self.type = token_type
        self.value = value
        self.line = line
        self.column = column
        self.filename = filename
    
    def __repr__(self) -> str:
        return f"Token({self.type.name}, '{self.value}', line={self.line}, col={self.column})"
    
    def __str__(self) -> str:
        value_str = str(self.value) if self.value is not None else "None"
        return f"[{self.type.name:20}] {value_str:20} at line {self.line:3}, col {self.column:3}"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value
        return False
    
    def is_type(self, *types: TokenType) -> bool:
        """Check if token matches any of the given types"""
        return self.type in types
    
    def location(self) -> str:
        """Return formatted location string"""
        return f"{self.filename}:{self.line}:{self.column}"