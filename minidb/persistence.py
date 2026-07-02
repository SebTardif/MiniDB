"""Persistence layer for MiniDB."""

import json
from typing import TYPE_CHECKING, Any

from .errors import FileReadError, FileWriteError, VersionMismatchError

if TYPE_CHECKING:
    from .database import MiniDB

CURRENT_VERSION = '1.0'


def save_database(db: 'MiniDB', filepath: str) -> None:
    """
    Save a database to a JSON file.

    Args:
        db: The database to save
        filepath: Path to the output file

    Raises:
        FileWriteError: If the file cannot be written
    """
    data: dict[str, Any] = {'version': CURRENT_VERSION, 'tables': {}}

    for table_name, table in db._tables.items():
        data['tables'][table_name] = table.to_dict()

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        raise FileWriteError(filepath, str(e)) from e
    except (TypeError, ValueError) as e:
        raise FileWriteError(filepath, f'Serialization error: {e}') from e


def load_database(filepath: str) -> 'MiniDB':
    """
    Load a database from a JSON file.

    Args:
        filepath: Path to the input file

    Returns:
        The loaded database

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

    # Import here to avoid circular import
    from .database import MiniDB
    from .table import Table

    db = MiniDB()

    # Load tables
    for table_name, table_data in data.get('tables', {}).items():
        table = Table.from_dict(table_data)
        db._tables[table_name] = table

    return db


def export_to_json(db: 'MiniDB', filepath: str) -> None:
    """
    Export database to a human-readable JSON format.

    This is an alias for save_database.
    """
    save_database(db, filepath)


def import_from_json(filepath: str) -> 'MiniDB':
    """
    Import database from a human-readable JSON format.

    This is an alias for load_database.
    """
    return load_database(filepath)
