"""Column definition and schema management for MiniDB."""

from dataclasses import dataclass, field
from typing import Any

from .errors import NullValueError, TypeMismatchError
from .types import ColumnType


@dataclass
class Column:
    """Represents a column definition in a table."""

    name: str
    type: ColumnType
    primary_key: bool = False
    nullable: bool = True
    default: Any = None

    def __post_init__(self):
        """Validate column definition after initialization."""
        if self.primary_key and not self.nullable:
            # Primary keys are implicitly NOT NULL
            pass
        if self.primary_key:
            self.nullable = False

    def validate(self, value: Any) -> Any:
        """
        Validate and optionally cast a value for this column.

        Args:
            value: The value to validate

        Returns:
            The validated (and possibly cast) value

        Raises:
            NullValueError: If value is None and column is not nullable
            TypeMismatchError: If value cannot be cast to the column type
        """
        if value is None:
            if not self.nullable:
                raise NullValueError(self.name)
            return None

        # Try to cast the value to the correct type
        try:
            cast_value = self.type.cast(value)
        except (ValueError, TypeError) as e:
            raise TypeMismatchError(self.name, self.type.name, type(value).__name__) from e

        return cast_value

    def to_dict(self) -> dict:
        """Serialize column to a dictionary."""
        return {
            'name': self.name,
            'type': self.type.name,
            'primary_key': self.primary_key,
            'nullable': self.nullable,
            'default': self.default,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Column':
        """Deserialize column from a dictionary."""
        return cls(
            name=data['name'],
            type=ColumnType[data['type']],
            primary_key=data.get('primary_key', False),
            nullable=data.get('nullable', True),
            default=data.get('default'),
        )


@dataclass
class Schema:
    """Represents a table schema with multiple columns."""

    columns: list[Column] = field(default_factory=list)
    _column_map: dict[str, Column] = field(default_factory=dict, repr=False)
    _primary_key: str | None = field(default=None, repr=False)

    def __post_init__(self):
        """Build internal structures after initialization."""
        self._rebuild_indexes()

    def _rebuild_indexes(self):
        """Rebuild internal indexes for fast lookups."""
        self._column_map = {col.name: col for col in self.columns}
        self._primary_key = None
        for col in self.columns:
            if col.primary_key:
                self._primary_key = col.name
                break

    def add_column(self, column: Column) -> None:
        """Add a column to the schema."""
        if column.name in self._column_map:
            raise ValueError(f"Column '{column.name}' already exists")
        self.columns.append(column)
        self._column_map[column.name] = column
        if column.primary_key:
            self._primary_key = column.name

    def get_column(self, name: str) -> Column | None:
        """Get a column by name."""
        return self._column_map.get(name)

    def has_column(self, name: str) -> bool:
        """Check if a column exists."""
        return name in self._column_map

    @property
    def primary_key(self) -> str | None:
        """Get the primary key column name, if any."""
        return self._primary_key

    @property
    def column_names(self) -> list[str]:
        """Get list of all column names."""
        return [col.name for col in self.columns]

    def validate_row(self, row: dict, allow_missing: bool = False) -> dict:
        """
        Validate a row against the schema.

        Args:
            row: The row data to validate
            allow_missing: If True, missing columns get default values

        Returns:
            A validated row with all columns present
        """
        validated = {}
        for col in self.columns:
            if col.name in row:
                validated[col.name] = col.validate(row[col.name])
            elif allow_missing:
                if col.default is not None:
                    validated[col.name] = col.default
                elif col.nullable:
                    validated[col.name] = None
                else:
                    raise NullValueError(col.name)
            else:
                raise ValueError(f'Missing column: {col.name}')
        return validated

    def to_dict(self) -> dict:
        """Serialize schema to a dictionary."""
        return {'columns': [col.to_dict() for col in self.columns]}

    @classmethod
    def from_dict(cls, data: dict) -> 'Schema':
        """Deserialize schema from a dictionary."""
        columns = [Column.from_dict(col_data) for col_data in data['columns']]
        return cls(columns=columns)
