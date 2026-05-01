"""SQL parser for MiniDB."""

from dataclasses import dataclass, field
from typing import Any

from .errors import SyntaxError_
from .types import ColumnType, TokenType


@dataclass
class Token:
    """Represents a single token from the lexer."""

    type: TokenType
    value: Any
    position: int


@dataclass
class Condition:
    """Represents a WHERE condition."""

    column: str
    operator: str  # '=', '!=', '>', '>=', '<', '<=', 'LIKE', 'IN'
    value: Any
    table_alias: str | None = None  # For JOIN column references


@dataclass
class WhereClause:
    """Represents a WHERE clause with AND/OR logic."""

    conditions: list  # List of Condition or WhereClause (nested)
    operator: str = 'AND'  # 'AND' or 'OR'


@dataclass
class JoinClause:
    """Represents a JOIN clause."""

    table: str
    left_column: str
    right_column: str
    join_type: str = 'INNER'  # 'INNER', 'LEFT', 'RIGHT'
    left_table: str | None = None
    right_table: str | None = None


@dataclass
class OrderByItem:
    """Represents an ORDER BY item."""

    column: str
    direction: str = 'ASC'
    table_alias: str | None = None


@dataclass
class AggregateFunction:
    """Represents an aggregate function call."""

    function: str  # 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'
    column: str  # Column name or '*' for COUNT(*)
    alias: str | None = None


@dataclass
class SelectColumn:
    """Represents a column in a SELECT statement."""

    name: str  # Column name or '*'
    table_alias: str | None = None
    aggregate: AggregateFunction | None = None
    alias: str | None = None


@dataclass
class SelectQuery:
    """Represents a parsed SELECT query."""

    columns: list[SelectColumn]
    table: str
    where: WhereClause | None = None
    order_by: list[OrderByItem] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    limit: int | None = None
    joins: list[JoinClause] = field(default_factory=list)


@dataclass
class InsertQuery:
    """Represents a parsed INSERT query."""

    table: str
    columns: list[str]
    values: list[Any]


@dataclass
class UpdateQuery:
    """Represents a parsed UPDATE query."""

    table: str
    set_clause: dict[str, Any]
    where: WhereClause | None = None


@dataclass
class DeleteQuery:
    """Represents a parsed DELETE query."""

    table: str
    where: WhereClause | None = None


@dataclass
class ColumnDef:
    """Represents a column definition in CREATE TABLE."""

    name: str
    type: ColumnType
    primary_key: bool = False
    nullable: bool = True


@dataclass
class CreateTableQuery:
    """Represents a parsed CREATE TABLE query."""

    table: str
    columns: list[ColumnDef]


@dataclass
class DropTableQuery:
    """Represents a parsed DROP TABLE query."""

    table: str


class Lexer:
    """Tokenizes SQL queries."""

    KEYWORDS = {
        'SELECT': TokenType.SELECT,
        'FROM': TokenType.FROM,
        'WHERE': TokenType.WHERE,
        'INSERT': TokenType.INSERT,
        'INTO': TokenType.INTO,
        'VALUES': TokenType.VALUES,
        'UPDATE': TokenType.UPDATE,
        'SET': TokenType.SET,
        'DELETE': TokenType.DELETE,
        'CREATE': TokenType.CREATE,
        'TABLE': TokenType.TABLE,
        'DROP': TokenType.DROP,
        'ORDER': TokenType.ORDER,
        'BY': TokenType.BY,
        'GROUP': TokenType.GROUP,
        'JOIN': TokenType.JOIN,
        'INNER': TokenType.INNER,
        'LEFT': TokenType.LEFT,
        'RIGHT': TokenType.RIGHT,
        'ON': TokenType.ON,
        'AND': TokenType.AND,
        'OR': TokenType.OR,
        'NOT': TokenType.NOT,
        'IN': TokenType.IN,
        'LIKE': TokenType.LIKE,
        'ASC': TokenType.ASC,
        'DESC': TokenType.DESC,
        'PRIMARY': TokenType.PRIMARY,
        'KEY': TokenType.KEY,
        'NULL': TokenType.NULL,
        'LIMIT': TokenType.LIMIT,
    }

    def __init__(self, sql: str):
        self.sql = sql
        self.pos = 0
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        """Tokenize the SQL string."""
        while self.pos < len(self.sql):
            self._skip_whitespace()
            if self.pos >= len(self.sql):
                break

            char = self.sql[self.pos]

            # String literal
            if char in ('"', "'"):
                self._read_string(char)
            # Number
            elif char.isdigit() or (char == '-' and self.pos + 1 < len(self.sql) and self.sql[self.pos + 1].isdigit()):
                self._read_number()
            # Identifier or keyword
            elif char.isalpha() or char == '_':
                self._read_identifier()
            # Operators and punctuation
            elif char == '=':
                self.tokens.append(Token(TokenType.EQUALS, '=', self.pos))
                self.pos += 1
            elif char == '!':
                if self.pos + 1 < len(self.sql) and self.sql[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.NOT_EQUALS, '!=', self.pos))
                    self.pos += 2
                else:
                    raise SyntaxError_("Unexpected character '!'", self.pos)
            elif char == '>':
                if self.pos + 1 < len(self.sql) and self.sql[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.GREATER_EQUAL, '>=', self.pos))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.GREATER, '>', self.pos))
                    self.pos += 1
            elif char == '<':
                if self.pos + 1 < len(self.sql) and self.sql[self.pos + 1] == '=':
                    self.tokens.append(Token(TokenType.LESS_EQUAL, '<=', self.pos))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.LESS, '<', self.pos))
                    self.pos += 1
            elif char == ',':
                self.tokens.append(Token(TokenType.COMMA, ',', self.pos))
                self.pos += 1
            elif char == '.':
                self.tokens.append(Token(TokenType.DOT, '.', self.pos))
                self.pos += 1
            elif char == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', self.pos))
                self.pos += 1
            elif char == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', self.pos))
                self.pos += 1
            elif char == ';':
                self.tokens.append(Token(TokenType.SEMICOLON, ';', self.pos))
                self.pos += 1
            elif char == '*':
                self.tokens.append(Token(TokenType.STAR, '*', self.pos))
                self.pos += 1
            else:
                raise SyntaxError_(f"Unexpected character: '{char}'", self.pos)

        self.tokens.append(Token(TokenType.EOF, None, self.pos))
        return self.tokens

    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self.pos < len(self.sql) and self.sql[self.pos].isspace():
            self.pos += 1

    def _read_string(self, quote_char: str):
        """Read a string literal."""
        start = self.pos
        self.pos += 1  # Skip opening quote
        value = []

        while self.pos < len(self.sql):
            char = self.sql[self.pos]
            if char == quote_char:
                # Check for escaped quote
                if self.pos + 1 < len(self.sql) and self.sql[self.pos + 1] == quote_char:
                    value.append(quote_char)
                    self.pos += 2
                else:
                    self.pos += 1  # Skip closing quote
                    break
            elif char == '\\' and self.pos + 1 < len(self.sql):
                # Handle escape sequences
                next_char = self.sql[self.pos + 1]
                if next_char == 'n':
                    value.append('\n')
                elif next_char == 't':
                    value.append('\t')
                elif next_char == '\\':
                    value.append('\\')
                elif next_char == quote_char:
                    value.append(quote_char)
                else:
                    value.append(next_char)
                self.pos += 2
            else:
                value.append(char)
                self.pos += 1
        else:
            raise SyntaxError_('Unterminated string literal', start)

        self.tokens.append(Token(TokenType.STRING_LITERAL, ''.join(value), start))

    def _read_number(self):
        """Read a numeric literal."""
        start = self.pos
        value = []

        if self.sql[self.pos] == '-':
            value.append('-')
            self.pos += 1

        while self.pos < len(self.sql) and self.sql[self.pos].isdigit():
            value.append(self.sql[self.pos])
            self.pos += 1

        # Check for decimal
        if self.pos < len(self.sql) and self.sql[self.pos] == '.':
            value.append('.')
            self.pos += 1
            while self.pos < len(self.sql) and self.sql[self.pos].isdigit():
                value.append(self.sql[self.pos])
                self.pos += 1
            self.tokens.append(Token(TokenType.FLOAT_LITERAL, float(''.join(value)), start))
        else:
            self.tokens.append(Token(TokenType.INTEGER_LITERAL, int(''.join(value)), start))

    def _read_identifier(self):
        """Read an identifier or keyword."""
        start = self.pos
        value = []

        while self.pos < len(self.sql) and (self.sql[self.pos].isalnum() or self.sql[self.pos] == '_'):
            value.append(self.sql[self.pos])
            self.pos += 1

        identifier = ''.join(value)
        upper = identifier.upper()

        # Check for keywords
        if upper in self.KEYWORDS:
            self.tokens.append(Token(self.KEYWORDS[upper], upper, start))
        # Check for boolean literals
        elif upper == 'TRUE':
            self.tokens.append(Token(TokenType.BOOLEAN_LITERAL, True, start))
        elif upper == 'FALSE':
            self.tokens.append(Token(TokenType.BOOLEAN_LITERAL, False, start))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, identifier, start))


class Parser:
    """Parses tokenized SQL queries."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> SelectQuery | InsertQuery | UpdateQuery | DeleteQuery | CreateTableQuery | DropTableQuery:
        """Parse the token stream into a query object."""
        token = self._current()

        if token.type == TokenType.SELECT:
            return self._parse_select()
        elif token.type == TokenType.INSERT:
            return self._parse_insert()
        elif token.type == TokenType.UPDATE:
            return self._parse_update()
        elif token.type == TokenType.DELETE:
            return self._parse_delete()
        elif token.type == TokenType.CREATE:
            return self._parse_create()
        elif token.type == TokenType.DROP:
            return self._parse_drop()
        else:
            raise SyntaxError_(f'Unexpected token: {token.value}', token.position)

    def _current(self) -> Token:
        """Get the current token."""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]

    def _peek(self, offset: int = 1) -> Token:
        """Peek at a future token."""
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else self.tokens[-1]

    def _advance(self) -> Token:
        """Advance to the next token and return the previous one."""
        token = self._current()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type."""
        token = self._current()
        if token.type != token_type:
            raise SyntaxError_(f'Expected {token_type.name}, got {token.type.name}', token.position)
        return self._advance()

    def _match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self._current().type in token_types

    def _parse_select(self) -> SelectQuery:
        """Parse a SELECT query."""
        self._expect(TokenType.SELECT)

        # Parse columns
        columns = self._parse_select_columns()

        # FROM clause
        self._expect(TokenType.FROM)
        table_token = self._expect(TokenType.IDENTIFIER)
        table = table_token.value

        # JOIN clauses
        joins = []
        while self._match(TokenType.JOIN, TokenType.INNER, TokenType.LEFT, TokenType.RIGHT):
            joins.append(self._parse_join())

        # WHERE clause
        where = None
        if self._match(TokenType.WHERE):
            self._advance()
            where = self._parse_where()

        # GROUP BY clause
        group_by = []
        if self._match(TokenType.GROUP):
            self._advance()
            self._expect(TokenType.BY)
            group_by = self._parse_group_by()

        # ORDER BY clause
        order_by = []
        if self._match(TokenType.ORDER):
            self._advance()
            self._expect(TokenType.BY)
            order_by = self._parse_order_by()

        # LIMIT clause
        limit = None
        if self._match(TokenType.LIMIT):
            self._advance()
            limit_token = self._expect(TokenType.INTEGER_LITERAL)
            limit = limit_token.value

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return SelectQuery(
            columns=columns, table=table, where=where, order_by=order_by, group_by=group_by, limit=limit, joins=joins
        )

    def _parse_select_columns(self) -> list[SelectColumn]:
        """Parse SELECT column list."""
        columns = []

        while True:
            col = self._parse_select_column()
            columns.append(col)

            if not self._match(TokenType.COMMA):
                break
            self._advance()

        return columns

    def _parse_select_column(self) -> SelectColumn:
        """Parse a single SELECT column."""
        # Check for aggregate functions
        if self._match(TokenType.IDENTIFIER):
            name = self._current().value.upper()
            if name in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
                return self._parse_aggregate_column()

        # Check for *
        if self._match(TokenType.STAR):
            self._advance()
            return SelectColumn(name='*')

        # Check for table.column or just column
        table_alias = None
        col_name = self._expect(TokenType.IDENTIFIER).value

        if self._match(TokenType.DOT):
            self._advance()
            if self._match(TokenType.STAR):
                self._advance()
                return SelectColumn(name='*', table_alias=col_name)
            table_alias = col_name
            col_name = self._expect(TokenType.IDENTIFIER).value

        # Check for alias (AS keyword)
        alias = None
        if self._match(TokenType.IDENTIFIER) and self._current().value.upper() != 'FROM':
            alias = self._advance().value
        elif self._peek().type == TokenType.IDENTIFIER and self._peek().value.upper() == 'AS':
            pass  # Skip AS keyword handling for now

        return SelectColumn(name=col_name, table_alias=table_alias, alias=alias)

    def _parse_aggregate_column(self) -> SelectColumn:
        """Parse an aggregate function column."""
        func_name = self._advance().value.upper()
        self._expect(TokenType.LPAREN)

        table_alias = None
        if self._match(TokenType.STAR):
            self._advance()
            col_name = '*'
        else:
            col_name = self._expect(TokenType.IDENTIFIER).value
            # Check for table.column syntax
            if self._match(TokenType.DOT):
                self._advance()
                table_alias = col_name
                col_name = self._expect(TokenType.IDENTIFIER).value

        self._expect(TokenType.RPAREN)

        # Check for alias
        alias = None
        if self._match(TokenType.IDENTIFIER):
            alias = self._advance().value

        return SelectColumn(
            name=col_name,
            table_alias=table_alias,
            aggregate=AggregateFunction(function=func_name, column=col_name, alias=alias),
        )

    def _parse_join(self) -> JoinClause:
        """Parse a JOIN clause."""
        join_type = 'INNER'

        if self._match(TokenType.LEFT):
            join_type = 'LEFT'
            self._advance()
        elif self._match(TokenType.RIGHT):
            join_type = 'RIGHT'
            self._advance()
        elif self._match(TokenType.INNER):
            self._advance()

        self._expect(TokenType.JOIN)
        right_table = self._expect(TokenType.IDENTIFIER).value

        self._expect(TokenType.ON)

        # Parse join condition: left_col = right_col
        left_col = self._expect(TokenType.IDENTIFIER).value
        left_table = None
        if self._match(TokenType.DOT):
            self._advance()
            left_table = left_col
            left_col = self._expect(TokenType.IDENTIFIER).value

        self._expect(TokenType.EQUALS)

        right_col = self._expect(TokenType.IDENTIFIER).value
        right_table_alias = None
        if self._match(TokenType.DOT):
            self._advance()
            right_table_alias = right_col
            right_col = self._expect(TokenType.IDENTIFIER).value

        return JoinClause(
            table=right_table,
            left_column=left_col,
            right_column=right_col,
            join_type=join_type,
            left_table=left_table,
            right_table=right_table_alias or right_table,
        )

    def _parse_where(self) -> WhereClause:
        """Parse a WHERE clause."""
        conditions = [self._parse_condition()]
        operator = 'AND'

        while self._match(TokenType.AND, TokenType.OR):
            if self._current().type == TokenType.AND:
                operator = 'AND'
            else:
                operator = 'OR'
            self._advance()
            conditions.append(self._parse_condition())

        return WhereClause(conditions=conditions, operator=operator)

    def _parse_condition(self) -> Condition:
        """Parse a single condition."""
        # Check for NOT
        if self._match(TokenType.NOT):
            self._advance()

        # Parse column (possibly with table prefix)
        table_alias = None
        column = self._expect(TokenType.IDENTIFIER).value

        if self._match(TokenType.DOT):
            self._advance()
            table_alias = column
            column = self._expect(TokenType.IDENTIFIER).value

        # Parse operator
        if self._match(TokenType.EQUALS):
            op = '='
            self._advance()
        elif self._match(TokenType.NOT_EQUALS):
            op = '!='
            self._advance()
        elif self._match(TokenType.GREATER):
            op = '>'
            self._advance()
        elif self._match(TokenType.GREATER_EQUAL):
            op = '>='
            self._advance()
        elif self._match(TokenType.LESS):
            op = '<'
            self._advance()
        elif self._match(TokenType.LESS_EQUAL):
            op = '<='
            self._advance()
        elif self._match(TokenType.LIKE):
            op = 'LIKE'
            self._advance()
        elif self._match(TokenType.IN):
            op = 'IN'
            self._advance()
        else:
            raise SyntaxError_(
                f'Expected comparison operator, got {self._current().type.name}', self._current().position
            )

        # Parse value
        if op == 'IN':
            self._expect(TokenType.LPAREN)
            values = []
            while True:
                values.append(self._parse_value())
                if not self._match(TokenType.COMMA):
                    break
                self._advance()
            self._expect(TokenType.RPAREN)
            value = values
        else:
            value = self._parse_value()

        return Condition(column=column, operator=op, value=value, table_alias=table_alias)

    def _parse_value(self) -> Any:
        """Parse a literal value."""
        token = self._current()

        if (
            token.type == TokenType.STRING_LITERAL
            or token.type == TokenType.INTEGER_LITERAL
            or token.type == TokenType.FLOAT_LITERAL
            or token.type == TokenType.BOOLEAN_LITERAL
        ):
            self._advance()
            return token.value
        elif token.type == TokenType.NULL:
            self._advance()
            return None
        else:
            raise SyntaxError_(f'Expected literal value, got {token.type.name}', token.position)

    def _parse_group_by(self) -> list[str]:
        """Parse GROUP BY columns."""
        columns = []
        while True:
            columns.append(self._expect(TokenType.IDENTIFIER).value)
            if not self._match(TokenType.COMMA):
                break
            self._advance()
        return columns

    def _parse_order_by(self) -> list[OrderByItem]:
        """Parse ORDER BY clause."""
        items = []
        while True:
            column = self._expect(TokenType.IDENTIFIER).value
            table_alias = None

            if self._match(TokenType.DOT):
                self._advance()
                table_alias = column
                column = self._expect(TokenType.IDENTIFIER).value

            direction = 'ASC'
            if self._match(TokenType.ASC):
                self._advance()
            elif self._match(TokenType.DESC):
                self._advance()
                direction = 'DESC'

            items.append(OrderByItem(column=column, direction=direction, table_alias=table_alias))

            if not self._match(TokenType.COMMA):
                break
            self._advance()

        return items

    def _parse_insert(self) -> InsertQuery:
        """Parse an INSERT query."""
        self._expect(TokenType.INSERT)
        self._expect(TokenType.INTO)

        table = self._expect(TokenType.IDENTIFIER).value

        # Parse columns
        self._expect(TokenType.LPAREN)
        columns = []
        while True:
            columns.append(self._expect(TokenType.IDENTIFIER).value)
            if not self._match(TokenType.COMMA):
                break
            self._advance()
        self._expect(TokenType.RPAREN)

        # Parse VALUES
        self._expect(TokenType.VALUES)
        self._expect(TokenType.LPAREN)
        values = []
        while True:
            values.append(self._parse_value())
            if not self._match(TokenType.COMMA):
                break
            self._advance()
        self._expect(TokenType.RPAREN)

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return InsertQuery(table=table, columns=columns, values=values)

    def _parse_update(self) -> UpdateQuery:
        """Parse an UPDATE query."""
        self._expect(TokenType.UPDATE)
        table = self._expect(TokenType.IDENTIFIER).value

        # Parse SET clause
        self._expect(TokenType.SET)
        set_clause = {}
        while True:
            col = self._expect(TokenType.IDENTIFIER).value
            self._expect(TokenType.EQUALS)
            val = self._parse_value()
            set_clause[col] = val

            if not self._match(TokenType.COMMA):
                break
            self._advance()

        # Parse WHERE clause
        where = None
        if self._match(TokenType.WHERE):
            self._advance()
            where = self._parse_where()

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return UpdateQuery(table=table, set_clause=set_clause, where=where)

    def _parse_delete(self) -> DeleteQuery:
        """Parse a DELETE query."""
        self._expect(TokenType.DELETE)
        self._expect(TokenType.FROM)

        table = self._expect(TokenType.IDENTIFIER).value

        # Parse WHERE clause
        where = None
        if self._match(TokenType.WHERE):
            self._advance()
            where = self._parse_where()

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return DeleteQuery(table=table, where=where)

    def _parse_create(self) -> CreateTableQuery:
        """Parse a CREATE TABLE query."""
        self._expect(TokenType.CREATE)
        self._expect(TokenType.TABLE)

        table = self._expect(TokenType.IDENTIFIER).value

        # Parse column definitions
        self._expect(TokenType.LPAREN)
        columns = []
        while True:
            col = self._parse_column_def()
            columns.append(col)

            if not self._match(TokenType.COMMA):
                break
            self._advance()
        self._expect(TokenType.RPAREN)

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return CreateTableQuery(table=table, columns=columns)

    def _parse_column_def(self) -> ColumnDef:
        """Parse a column definition."""
        name = self._expect(TokenType.IDENTIFIER).value
        type_str = self._expect(TokenType.IDENTIFIER).value
        col_type = ColumnType.from_string(type_str)

        primary_key = False
        nullable = True

        # Check for PRIMARY KEY
        if self._match(TokenType.PRIMARY):
            self._advance()
            self._expect(TokenType.KEY)
            primary_key = True
            nullable = False

        # Check for NULL/NOT NULL
        if self._match(TokenType.NOT):
            self._advance()
            self._expect(TokenType.NULL)
            nullable = False
        elif self._match(TokenType.NULL):
            self._advance()
            nullable = True

        return ColumnDef(name=name, type=col_type, primary_key=primary_key, nullable=nullable)

    def _parse_drop(self) -> DropTableQuery:
        """Parse a DROP TABLE query."""
        self._expect(TokenType.DROP)
        self._expect(TokenType.TABLE)

        table = self._expect(TokenType.IDENTIFIER).value

        # Optional semicolon
        if self._match(TokenType.SEMICOLON):
            self._advance()

        return DropTableQuery(table=table)


def parse_sql(sql: str) -> SelectQuery | InsertQuery | UpdateQuery | DeleteQuery | CreateTableQuery | DropTableQuery:
    """Parse a SQL string into a query object."""
    lexer = Lexer(sql)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()
