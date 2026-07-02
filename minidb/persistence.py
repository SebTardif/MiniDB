"""Persistence layer for MiniDB."""

import json
from typing import Any

from .errors import FileReadError, FileWriteError, VersionMismatchError
from .table import Table

CURRENT_VERSION = '1.0'


def _serialize(tables: dict[str, Table], filepath: str) -> None:
    """
    Serialize tables to a JSON file.

    Args:
        tables: Mapping of table names to Table objects
        filepath: Path to the output file

    Raises:
        FileWriteError: If the file cannot be written
    """
    data: dict[str, Any] = {'version': CURRENT_VERSION, 'tables': {}}

    for table_name, table in tables.items():
        data['tables'][table_name] = table.to_dict()

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        raise FileWriteError(filepath, str(e)) from e
    except (TypeError, ValueError) as e:
        raise FileWriteError(filepath, f'Serialization error: {e}') from e


def _deserialize(filepath: str) -> dict[str, Table]:
    """
    Deserialize tables from a JSON file.

    Args:
        filepath: Path to the input file

    Returns:
        Mapping of table names to Table objects

    Raises:
        FileReadError: If the file cannot be read
        VersionMismatchError: If the file version is incompatible
    """
    try:
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise FileReadError(filepath, 'File not found') from e
    except OSError as e:
        raise FileReadError(filepath, str(e)) from e
    except json.JSONDecodeError as e:
        raise FileReadError(filepath, f'Invalid JSON: {e}') from e

    # Check version
    version = data.get('version', 'unknown')
    if version != CURRENT_VERSION:
        raise VersionMismatchError(version, CURRENT_VERSION)

    tables: dict[str, Table] = {}
    for table_name, table_data in data.get('tables', {}).items():
        tables[table_name] = Table.from_dict(table_data)

    return tables
