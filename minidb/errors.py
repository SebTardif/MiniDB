"""Custom exceptions for MiniDB."""


class MiniDBError(Exception):
    """Base exception for all MiniDB errors."""
    pass


class TableError(MiniDBError):
    """Errors related to table operations."""
    pass


class TableNotFoundError(TableError):
    """Raised when a table does not exist."""
    def __init__(self, table_name: str):
        self.table_name = table_name
        super().__init__(f"Table '{table_name}' not found")


class TableExistsError(TableError):
    """Raised when a table already exists."""
    def __init__(self, table_name: str):
        self.table_name = table_name
        super().__init__(f"Table '{table_name}' already exists")


class ColumnError(MiniDBError):
    """Errors related to column operations."""
    pass


class ColumnNotFoundError(ColumnError):
    """Raised when a column does not exist."""
    def __init__(self, column_name: str, table_name: str = None):
        self.column_name = column_name
        self.table_name = table_name
        msg = f"Column '{column_name}' not found"
        if table_name:
            msg += f" in table '{table_name}'"
        super().__init__(msg)


class ColumnExistsError(ColumnError):
    """Raised when a column already exists."""
    def __init__(self, column_name: str, table_name: str):
        self.column_name = column_name
        self.table_name = table_name
        super().__init__(f"Column '{column_name}' already exists in table '{table_name}'")


class TypeError_(MiniDBError):
    """Errors related to type validation."""
    pass


class TypeMismatchError(TypeError_):
    """Raised when a value doesn't match the column type."""
    def __init__(self, column_name: str, expected_type: str, actual_type: str):
        self.column_name = column_name
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            f"Type mismatch for column '{column_name}': "
            f"expected {expected_type}, got {actual_type}"
        )


class NullValueError(TypeError_):
    """Raised when a NULL value is provided for a non-nullable column."""
    def __init__(self, column_name: str):
        self.column_name = column_name
        super().__init__(f"NULL value not allowed for column '{column_name}'")


class ParseError(MiniDBError):
    """Errors related to SQL parsing."""
    pass


class SyntaxError_(ParseError):
    """Raised when there's a syntax error in the SQL query."""
    def __init__(self, message: str, position: int = None):
        self.position = position
        msg = f"Syntax error: {message}"
        if position is not None:
            msg += f" at position {position}"
        super().__init__(msg)


class QueryError(MiniDBError):
    """Errors related to query execution."""
    pass


class InvalidQueryError(QueryError):
    """Raised when a query is invalid."""
    def __init__(self, message: str):
        super().__init__(f"Invalid query: {message}")


class AmbiguousColumnError(QueryError):
    """Raised when a column reference is ambiguous."""
    def __init__(self, column_name: str):
        self.column_name = column_name
        super().__init__(f"Ambiguous column reference: '{column_name}'")


class ConstraintError(MiniDBError):
    """Errors related to constraint violations."""
    pass


class PrimaryKeyError(ConstraintError):
    """Raised when a primary key constraint is violated."""
    def __init__(self, message: str):
        super().__init__(f"Primary key constraint violation: {message}")


class DuplicateKeyError(PrimaryKeyError):
    """Raised when a duplicate primary key is inserted."""
    def __init__(self, key_value):
        self.key_value = key_value
        super().__init__(f"Duplicate primary key value: {key_value}")


class PersistenceError(MiniDBError):
    """Errors related to persistence operations."""
    pass


class FileReadError(PersistenceError):
    """Raised when a file cannot be read."""
    def __init__(self, filepath: str, reason: str = None):
        self.filepath = filepath
        msg = f"Failed to read file: {filepath}"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg)


class FileWriteError(PersistenceError):
    """Raised when a file cannot be written."""
    def __init__(self, filepath: str, reason: str = None):
        self.filepath = filepath
        msg = f"Failed to write file: {filepath}"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg)


class VersionMismatchError(PersistenceError):
    """Raised when the persistence file version is incompatible."""
    def __init__(self, version: str, expected: str):
        self.version = version
        self.expected = expected
        super().__init__(
            f"Incompatible persistence file version: {version} "
            f"(expected {expected})"
        )
