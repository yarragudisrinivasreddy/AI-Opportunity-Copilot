"""Tiny field-path resolver for rationale citation checks (e.g. 'risks[1].mitigated')."""
import re
from typing import Any

_TOKEN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


def resolve(data: Any, path: str) -> tuple[bool, Any]:
    """Return (found, value). Empty path never resolves."""
    if not path or not path.strip():
        return False, None
    cursor = data
    pos = 0
    path = path.strip()
    while pos < len(path):
        if path[pos] == ".":
            pos += 1
            continue
        match = _TOKEN.match(path, pos)
        if not match:
            return False, None
        pos = match.end()
        name, index = match.group(1), match.group(2)
        if name is not None:
            if not isinstance(cursor, dict) or name not in cursor:
                return False, None
            cursor = cursor[name]
        else:
            idx = int(index)
            if not isinstance(cursor, list) or idx >= len(cursor):
                return False, None
            cursor = cursor[idx]
    return True, cursor
