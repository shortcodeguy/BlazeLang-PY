"""
Lexer/Tokenizer for BlazeLang
Converts source code into a stream of tokens
"""

from blazelang.tokens.token_types import Token, TokenType
from blazelang.errors.error_handler import LexerError


class Lexer:
    """Converts BlazeLang source code into tokens"""
    
    def __init__(self, source: str, filename: str = "<unknown>"):
        self.source = source
        self.filename = filename
        self.position = 0
        self.line = 1
        self.column = 1
        self.current_char = self.source[0] if source else None
        
        # Keywords mapping
        self.keywords = {
            'var': TokenType.VAR,
            'constant': TokenType.CONSTANT,
            'bind': TokenType.BIND,
            'if': TokenType.IF,
            'else': TokenType.ELSE,
            'while': TokenType.WHILE,
            'for': TokenType.FOR,
            'in': TokenType.IN,
            'Meta': TokenType.META,
            'Function': TokenType.FUNCTION,
            'function': TokenType.FUNCTION,
            'Class': TokenType.CLASS,
            'Struct': TokenType.STRUCT,
            'Enum': TokenType.ENUM,
            'Constructor': TokenType.CONSTRUCTOR,
            'return': TokenType.RETURN,
            'Break': TokenType.BREAK,
            'Continue': TokenType.CONTINUE,
            'Import': TokenType.IMPORT,
            'import': TokenType.IMPORT,
            'Export': TokenType.EXPORT,
            'export': TokenType.EXPORT,
            'from': TokenType.FROM,
            'as': TokenType.AS,
            'Default': TokenType.DEFAULT,
            'default': TokenType.DEFAULT,
            'Define': TokenType.DEFINE,
            'try': TokenType.TRY,
            'catch': TokenType.CATCH,
            'finally': TokenType.FINALLY,
            'throw': TokenType.THROW,
            'static': TokenType.STATIC,
            'async': TokenType.ASYNC,
            'await': TokenType.AWAIT,
            'public': TokenType.PUBLIC,
            'private': TokenType.PRIVATE,
            'protected': TokenType.PROTECTED,
            'override': TokenType.OVERRIDE,
            'this': TokenType.THIS,
            'super': TokenType.SUPER,
            'and': TokenType.AND,
            'or': TokenType.OR,
            'not': TokenType.NOT,
            'true': TokenType.BOOLEAN,
            'false': TokenType.BOOLEAN,
            'null': TokenType.NULL,
            'Reflect': TokenType.REFLECT,
            'accept': TokenType.ACCEPT,
            'expect': TokenType.EXPECT,
            'reject': TokenType.REJECT,
        }
    
    def advance(self):
        """Move to the next character in source"""
        self.position += 1
        if self.position < len(self.source):
            self.current_char = self.source[self.position]
            self.column += 1
        else:
            self.current_char = None
    
    def peek(self, offset: int = 1) -> str:
        """Look ahead without consuming characters"""
        peek_pos = self.position + offset
        if peek_pos < len(self.source):
            return self.source[peek_pos]
        return None
    
    def skip_whitespace(self):
        """Skip whitespace characters (spaces, tabs, carriage returns)"""
        while self.current_char and self.current_char in ' \t\r':
            self.advance()
    
    def skip_comment(self):
        """Skip single-line and multi-line comments"""
        if self.current_char == '/' and self.peek() == '/':
            # Single line comment
            while self.current_char and self.current_char != '\n':
                self.advance()
        elif self.current_char == '/' and self.peek() == '*':
            # Multi-line comment
            self.advance()  # Skip /
            self.advance()  # Skip *
            while self.current_char:
                if self.current_char == '*' and self.peek() == '/':
                    self.advance()  # Skip *
                    self.advance()  # Skip /
                    break
                if self.current_char == '\n':
                    self.line += 1
                    self.column = 1
                self.advance()
    
    def read_number(self) -> Token:
        """Read a number literal (integer or float)"""
        start_column = self.column
        start_pos = self.position
        is_float = False
        
        while self.current_char and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                if is_float:
                    break  # Second decimal point - stop
                is_float = True
            self.advance()
        
        number_str = self.source[start_pos:self.position]
        if is_float:
            return Token(TokenType.FLOAT, float(number_str), self.line, start_column, self.filename)
        return Token(TokenType.INTEGER, int(number_str), self.line, start_column, self.filename)
    
    def read_string(self) -> Token:
        """Read a string literal"""
        start_column = self.column
        quote_char = self.current_char  # " or '
        self.advance()  # Skip opening quote
        
        string_value = ''
        while self.current_char and self.current_char != quote_char:
            if self.current_char == '\\':
                self.advance()
                escape_chars = {
                    'n': '\n',
                    't': '\t',
                    '\\': '\\',
                    '"': '"',
                    "'": "'",
                    '{': '{',
                }
                string_value += escape_chars.get(self.current_char, self.current_char)
            elif self.current_char == '\n':
                self.line += 1
                self.column = 1
                string_value += '\n'
            else:
                string_value += self.current_char
            self.advance()
        
        if self.current_char != quote_char:
            raise LexerError(
                f"Unterminated string literal",
                self.line, start_column, self.filename
            )
        
        self.advance()  # Skip closing quote
        return Token(TokenType.STRING, string_value, self.line, start_column, self.filename)
    
    def read_identifier(self) -> Token:
        """Read an identifier or keyword"""
        start_column = self.column
        start_pos = self.position
        
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            self.advance()
        
        identifier = self.source[start_pos:self.position]
        
        # Check if it is a keyword
        token_type = self.keywords.get(identifier, TokenType.IDENTIFIER)
        
        # Set appropriate value based on token type
        if token_type == TokenType.BOOLEAN:
            value = (identifier == 'true')
        elif token_type == TokenType.NULL:
            value = None
        else:
            value = identifier
        
        return Token(token_type, value, self.line, start_column, self.filename)
    
    def get_next_token(self) -> Token:
        """Get the next token from source code"""
        while self.current_char:
            # Skip whitespace
            if self.current_char in ' \t\r':
                self.skip_whitespace()
                continue
            
            # Skip newlines
            if self.current_char == '\n':
                self.line += 1
                self.column = 1
                self.advance()
                continue
            
            # Skip comments
            if self.current_char == '/' and (self.peek() == '/' or self.peek() == '*'):
                self.skip_comment()
                continue
            
            # Numbers
            if self.current_char.isdigit():
                return self.read_number()
            
            # Strings
            if self.current_char in '"\'':
                return self.read_string()
            
            # Identifiers and keywords
            if self.current_char.isalpha() or self.current_char == '_':
                return self.read_identifier()
            
            # Multi-character operators
            col = self.column
            
            if self.current_char == '=' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.EQUALS, '==', self.line, col, self.filename)
            
            if self.current_char == '!' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.NOT_EQUALS, '!=', self.line, col, self.filename)
            
            if self.current_char == '>' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.GREATER_EQUALS, '>=', self.line, col, self.filename)
            
            if self.current_char == '<' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.LESS_EQUALS, '<=', self.line, col, self.filename)
            
            if self.current_char == '+' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.PLUS_ASSIGN, '+=', self.line, col, self.filename)
            
            if self.current_char == '-' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.MINUS_ASSIGN, '-=', self.line, col, self.filename)
            
            if self.current_char == '*' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.MULTIPLY_ASSIGN, '*=', self.line, col, self.filename)
            
            if self.current_char == '/' and self.peek() == '=':
                self.advance(); self.advance()
                return Token(TokenType.DIVIDE_ASSIGN, '/=', self.line, col, self.filename)
            
            if self.current_char == '*' and self.peek() == '*':
                self.advance(); self.advance()
                return Token(TokenType.POWER, '**', self.line, col, self.filename)

            # Logical operators: || and &&
            if self.current_char == '|' and self.peek() == '|':
                self.advance(); self.advance()
                return Token(TokenType.OR, '||', self.line, col, self.filename)

            if self.current_char == '&' and self.peek() == '&':
                self.advance(); self.advance()
                return Token(TokenType.AND, '&&', self.line, col, self.filename)
            
            # Single character tokens
            single_char_map = {
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
                '*': TokenType.MULTIPLY,
                '/': TokenType.DIVIDE,
                '%': TokenType.MODULO,
                '=': TokenType.ASSIGN,
                '!': TokenType.NOT,
                '>': TokenType.GREATER,
                '<': TokenType.LESS,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                '{': TokenType.LBRACE,
                '}': TokenType.RBRACE,
                '[': TokenType.LBRACKET,
                ']': TokenType.RBRACKET,
                ',': TokenType.COMMA,
                '.': TokenType.DOT,
                ':': TokenType.COLON,
                '@': TokenType.AT,
                '^': TokenType.POWER,
            }
            
            if self.current_char in single_char_map:
                token_type = single_char_map[self.current_char]
                token = Token(token_type, self.current_char, self.line, col, self.filename)
                self.advance()
                return token
            
            # Unknown character
            raise LexerError(
                f"Unknown character '{self.current_char}'",
                self.line, self.column, self.filename
            )
        
        # End of file
        return Token(TokenType.EOF, None, self.line, self.column, self.filename)
    
    def tokenize(self) -> list:
        """Tokenize the entire source code"""
        tokens = []
        while True:
            token = self.get_next_token()
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens
