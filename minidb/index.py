"""Hash-based index implementation for MiniDB."""

from dataclasses import dataclass, field
from typing import Any, Optional
from bisect import bisect_left, bisect_right


@dataclass
class HashIndex:
    """
    Hash-based index for fast equality lookups.
    
    Maps values to sets of row IDs for O(1) equality lookups.
    For range queries, maintains a sorted list of keys.
    """
    column_name: str
    _index: dict[Any, set[int]] = field(default_factory=dict)
    _sorted_keys: list[Any] = field(default_factory=list)
    
    def insert(self, value: Any, row_id: int) -> None:
        """
        Add a row ID to the index for a given value.
        
        Args:
            value: The indexed value
            row_id: The row ID to associate with this value
        """
        if value not in self._index:
            self._index[value] = set()
            # Maintain sorted keys for range queries
            self._insert_sorted_key(value)
        self._index[value].add(row_id)
    
    def _insert_sorted_key(self, value: Any) -> None:
        """Insert a key into the sorted keys list."""
        pos = bisect_left(self._sorted_keys, value)
        if pos == len(self._sorted_keys) or self._sorted_keys[pos] != value:
            self._sorted_keys.insert(pos, value)
    
    def delete(self, value: Any, row_id: int) -> None:
        """
        Remove a row ID from the index for a given value.
        
        Args:
            value: The indexed value
            row_id: The row ID to remove
        """
        if value in self._index:
            self._index[value].discard(row_id)
            if not self._index[value]:
                del self._index[value]
                # Remove from sorted keys
                pos = bisect_left(self._sorted_keys, value)
                if pos < len(self._sorted_keys) and self._sorted_keys[pos] == value:
                    self._sorted_keys.pop(pos)
    
    def lookup(self, value: Any) -> set[int]:
        """
        Look up all row IDs for a given value.
        
        Args:
            value: The value to look up
            
        Returns:
            Set of row IDs, empty if value not found
        """
        return self._index.get(value, set()).copy()
    
    def range_lookup(self, op: str, value: Any) -> set[int]:
        """
        Look up row IDs for range conditions.
        
        Args:
            op: Comparison operator ('<', '<=', '>', '>=')
            value: The comparison value
            
        Returns:
            Set of row IDs matching the condition
        """
        result = set()
        
        if op == '<':
            # All keys less than value
            pos = bisect_left(self._sorted_keys, value)
            for key in self._sorted_keys[:pos]:
                result.update(self._index[key])
        elif op == '<=':
            # All keys less than or equal to value
            pos = bisect_right(self._sorted_keys, value)
            for key in self._sorted_keys[:pos]:
                result.update(self._index[key])
        elif op == '>':
            # All keys greater than value
            pos = bisect_right(self._sorted_keys, value)
            for key in self._sorted_keys[pos:]:
                result.update(self._index[key])
        elif op == '>=':
            # All keys greater than or equal to value
            pos = bisect_left(self._sorted_keys, value)
            for key in self._sorted_keys[pos:]:
                result.update(self._index[key])
        
        return result
    
    def has_value(self, value: Any) -> bool:
        """Check if a value exists in the index."""
        return value in self._index
    
    def clear(self) -> None:
        """Clear all entries from the index."""
        self._index.clear()
        self._sorted_keys.clear()
    
    def rebuild(self, rows: list[dict], row_ids: list[int]) -> None:
        """
        Rebuild the index from scratch.
        
        Args:
            rows: List of row dictionaries
            row_ids: Corresponding row IDs
        """
        self.clear()
        for row, row_id in zip(rows, row_ids):
            if self.column_name in row:
                value = row[self.column_name]
                if value is not None:
                    self.insert(value, row_id)
    
    @property
    def size(self) -> int:
        """Get the number of unique keys in the index."""
        return len(self._index)
    
    @property
    def total_entries(self) -> int:
        """Get the total number of indexed entries."""
        return sum(len(ids) for ids in self._index.values())


@dataclass
class IndexManager:
    """Manages multiple indexes for a table."""
    _indexes: dict[str, HashIndex] = field(default_factory=dict)
    
    def create_index(self, column_name: str) -> HashIndex:
        """
        Create a new index on a column.
        
        Args:
            column_name: Name of the column to index
            
        Returns:
            The created index
        """
        if column_name in self._indexes:
            raise ValueError(f"Index already exists on column '{column_name}'")
        index = HashIndex(column_name=column_name)
        self._indexes[column_name] = index
        return index
    
    def get_index(self, column_name: str) -> Optional[HashIndex]:
        """Get an index by column name."""
        return self._indexes.get(column_name)
    
    def has_index(self, column_name: str) -> bool:
        """Check if an index exists for a column."""
        return column_name in self._indexes
    
    def drop_index(self, column_name: str) -> None:
        """Drop an index by column name."""
        if column_name in self._indexes:
            del self._indexes[column_name]
    
    def insert_row(self, row: dict, row_id: int) -> None:
        """Insert a row into all indexes."""
        for column_name, index in self._indexes.items():
            if column_name in row and row[column_name] is not None:
                index.insert(row[column_name], row_id)
    
    def delete_row(self, row: dict, row_id: int) -> None:
        """Delete a row from all indexes."""
        for column_name, index in self._indexes.items():
            if column_name in row and row[column_name] is not None:
                index.delete(row[column_name], row_id)
    
    def update_row(self, old_row: dict, new_row: dict, row_id: int) -> None:
        """Update a row in all indexes."""
        for column_name, index in self._indexes.items():
            old_value = old_row.get(column_name)
            new_value = new_row.get(column_name)
            
            if old_value != new_value:
                if old_value is not None:
                    index.delete(old_value, row_id)
                if new_value is not None:
                    index.insert(new_value, row_id)
    
    def clear(self) -> None:
        """Clear all indexes."""
        for index in self._indexes.values():
            index.clear()
