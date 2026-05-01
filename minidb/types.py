"""Type definitions for MiniDB."""

from enum import Enum, auto
from typing import Any


class ColumnType(Enum):
    """Supported column types in MiniDB."""

    INTEGER = auto()
    STRING = auto()
    FLOAT = auto()
    BOOLEAN = auto()

    @classmethod
    def from_string(cls, type_str: str) -> 'ColumnType':
        """Convert a string representation to ColumnType."""
        type_map = {
            'INTEGER': cls.INTEGER,
            'INT': cls.INTEGER,
            'STRING': cls.STRING,
            'STR': cls.STRING,
            'TEXT': cls.STRING,
            'VARCHAR': cls.STRING,
            'FLOAT': cls.FLOAT,
            'DOUBLE': cls.FLOAT,
            'REAL': cls.FLOAT,
            'BOOLEAN': cls.BOOLEAN,
            'BOOL': cls.BOOLEAN,
        }
        upper_str = type_str.upper()
        if upper_str not in type_map:
            raise ValueError(f'Unknown column type: {type_str}')
        return type_map[upper_str]

    def to_string(self) -> str:
        """Convert ColumnType to string representation."""
        return self.name

    def validate(self, value: Any) -> bool:
        """Check if a value is valid for this column type."""
        if value is None:
            return True  # NULL values handled by nullable constraint

        type_validators = {
            ColumnType.INTEGER: lambda v: isinstance(v, int) and not isinstance(v, bool),
            ColumnType.STRING: lambda v: isinstance(v, str),
            ColumnType.FLOAT: lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            ColumnType.BOOLEAN: lambda v: isinstance(v, bool),
        }
        return type_validators[self](value)

    def cast(self, value: Any) -> Any:
        """Attempt to cast a value to this type."""
        if value is None:
            return None

        try:
            if self == ColumnType.INTEGER:
                if isinstance(value, bool):
                    return int(value)
                return int(value)
            elif self == ColumnType.STRING:
                return str(value)
            elif self == ColumnType.FLOAT:
                return float(value)
            elif self == ColumnType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes')
                return bool(value)
        except (ValueError, TypeError) as e:
            raise TypeError(f'Cannot cast {value!r} to {self.name}') from e

        return value


class TokenType(Enum):
    """Token types for the SQL lexer."""

    # Keywords
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    UPDATE = auto()
    SET = auto()
    DELETE = auto()
    CREATE = auto()
    TABLE = auto()
    DROP = auto()
    ORDER = auto()
    BY = auto()
    GROUP = auto()
    JOIN = auto()
    INNER = auto()
    LEFT = auto()
    RIGHT = auto()
    ON = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IN = auto()
    LIKE = auto()
    ASC = auto()
    DESC = auto()
    PRIMARY = auto()
    KEY = auto()
    NULL = auto()
    NOT_NULL = auto()
    LIMIT = auto()

    # Literals
    IDENTIFIER = auto()
    STRING_LITERAL = auto()
    INTEGER_LITERAL = auto()
    FLOAT_LITERAL = auto()
    BOOLEAN_LITERAL = auto()

    # Operators
    EQUALS = auto()
    NOT_EQUALS = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()

    # Punctuation
    COMMA = auto()
    DOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    SEMICOLON = auto()
    STAR = auto()

    # Special
    EOF = auto()


class QueryType(Enum):
    """Types of SQL queries."""

    SELECT = auto()
    INSERT = auto()
    UPDATE = auto()
    DELETE = auto()
    CREATE_TABLE = auto()
    DROP_TABLE = auto()


# Type alias for row data
Row = dict[str, Any]

# Type alias for query result
QueryResult = list[Row] | int | None
