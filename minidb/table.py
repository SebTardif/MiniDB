"""Table storage and row management for MiniDB."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .column import Schema
from .errors import DuplicateKeyError
from .index import IndexManager
from .types import Row


@dataclass
class Table:
    """
    Represents a database table with rows and a schema.

    Stores rows as dictionaries and maintains indexes for fast lookups.
    """

    name: str
    schema: Schema
    _rows: list[Row] = field(default_factory=list)
    _row_ids: list[int] = field(default_factory=list)
    _next_row_id: int = field(default=0)
    _index_manager: IndexManager = field(default_factory=IndexManager)

    def __post_init__(self):
        """Initialize indexes after table creation."""
        # Create index on primary key if exists
        if self.schema.primary_key:
            self._index_manager.create_index(self.schema.primary_key)

    @property
    def row_count(self) -> int:
        """Get the number of rows in the table."""
        return len(self._rows)

    @property
    def columns(self) -> list[str]:
        """Get list of column names."""
        return self.schema.column_names

    @property
    def primary_key(self) -> str | None:
        """Get the primary key column name."""
        return self.schema.primary_key

    def insert(self, row: dict) -> int:
        """
        Insert a new row into the table.

        Args:
            row: Row data as a dictionary

        Returns:
            The row ID of the inserted row

        Raises:
            DuplicateKeyError: If primary key already exists
        """
        # Validate and normalize the row
        validated_row = self.schema.validate_row(row, allow_missing=True)

        # Check for duplicate primary key
        pk_column = self.schema.primary_key
        if pk_column:
            pk_value = validated_row[pk_column]
            if pk_value is not None:
                index = self._index_manager.get_index(pk_column)
                if index and index.has_value(pk_value):
                    raise DuplicateKeyError(pk_value)

        # Assign row ID
        row_id = self._next_row_id
        self._next_row_id += 1

        # Store the row
        self._rows.append(validated_row)
        self._row_ids.append(row_id)

        # Update indexes
        self._index_manager.insert_row(validated_row, row_id)

        return row_id

    def get_row_by_id(self, row_id: int) -> Row | None:
        """Get a row by its ID."""
        try:
            idx = self._row_ids.index(row_id)
            return self._rows[idx].copy()
        except ValueError:
            return None

    def get_row_id_by_pk(self, pk_value: Any) -> int | None:
        """Get a row ID by primary key value."""
        pk_column = self.schema.primary_key
        if not pk_column:
            return None

        index = self._index_manager.get_index(pk_column)
        if not index:
            return None

        row_ids = index.lookup(pk_value)
        return next(iter(row_ids)) if row_ids else None

    def get_all_rows(self) -> list[Row]:
        """Get all rows in the table."""
        return [row.copy() for row in self._rows]

    def get_rows_with_ids(self) -> list[tuple[int, Row]]:
        """Get all rows with their IDs."""
        return [(row_id, row.copy()) for row_id, row in zip(self._row_ids, self._rows, strict=False)]

    def update_rows(self, row_ids: set[int], updates: dict) -> int:
        """
        Update rows with the given IDs.

        Args:
            row_ids: Set of row IDs to update
            updates: Dictionary of column updates

        Returns:
            Number of rows updated
        """
        if not row_ids or not updates:
            return 0

        count = 0
        for i, row_id in enumerate(self._row_ids):
            if row_id in row_ids:
                old_row = self._rows[i]
                new_row = old_row.copy()

                # Apply updates
                for col, val in updates.items():
                    if self.schema.has_column(col):
                        col_def = self.schema.get_column(col)
                        new_row[col] = col_def.validate(val)

                # Validate the new row
                validated = self.schema.validate_row(new_row, allow_missing=True)

                # Update indexes
                self._index_manager.update_row(old_row, validated, row_id)

                # Store the updated row
                self._rows[i] = validated
                count += 1

        return count

    def delete_rows(self, row_ids: set[int]) -> int:
        """
        Delete rows with the given IDs.

        Args:
            row_ids: Set of row IDs to delete

        Returns:
            Number of rows deleted
        """
        if not row_ids:
            return 0

        # Find indices to delete (in reverse order for safe removal)
        indices_to_delete = []
        for i, row_id in enumerate(self._row_ids):
            if row_id in row_ids:
                indices_to_delete.append(i)

        # Delete in reverse order
        count = 0
        for i in reversed(indices_to_delete):
            row = self._rows[i]
            row_id = self._row_ids[i]

            # Update indexes
            self._index_manager.delete_row(row, row_id)

            # Remove row
            self._rows.pop(i)
            self._row_ids.pop(i)
            count += 1

        return count

    def scan(self) -> Iterator[tuple[int, Row]]:
        """Iterate over all rows with their IDs."""
        for row_id, row in zip(self._row_ids, self._rows, strict=False):
            yield row_id, row.copy()

    def get_index(self, column_name: str):
        """Get an index for a column."""
        return self._index_manager.get_index(column_name)

    def has_index(self, column_name: str) -> bool:
        """Check if an index exists for a column."""
        return self._index_manager.has_index(column_name)

    def clear(self) -> None:
        """Remove all rows from the table."""
        self._rows.clear()
        self._row_ids.clear()
        self._next_row_id = 0
        self._index_manager.clear()

    def to_dict(self) -> dict:
        """Serialize table to a dictionary."""
        return {
            'name': self.name,
            'schema': self.schema.to_dict(),
            'rows': self._rows,
            'next_row_id': self._next_row_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Table':
        """Deserialize table from a dictionary."""
        schema = Schema.from_dict(data['schema'])
        table = cls(name=data['name'], schema=schema)
        table._rows = data['rows']
        table._next_row_id = data.get('next_row_id', len(table._rows))

        # Rebuild row IDs
        table._row_ids = list(range(len(table._rows)))

        # Rebuild indexes
        if table.schema.primary_key:
            index = table._index_manager.get_index(table.schema.primary_key)
            if index:
                index.rebuild(table._rows, table._row_ids)
            else:
                index = table._index_manager.create_index(table.schema.primary_key)
                index.rebuild(table._rows, table._row_ids)

        return table
