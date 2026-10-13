"""Shared, conservative bounds for user-supplied local import files."""
from __future__ import annotations

MAX_IMPORT_BYTES = 32 * 1024 * 1024
MAX_IMPORT_CHARS = 32 * 1024 * 1024
MAX_IMPORT_RECORDS = 100_000
MAX_SKIPPED_LINES = 10_000
MAX_FIELD_CHARS = 1_000_000
MAX_JSON_DEPTH = 128
MAX_JSON_NODES = 1_000_000
MAX_XML_DEPTH = 128
MAX_XML_ELEMENTS = 1_000_000


class ImportLimitError(ValueError):
    """Raised when an untrusted import exceeds a documented resource cap."""


def read_limited_bytes(path, max_bytes: int = MAX_IMPORT_BYTES) -> bytes:
    """Read at most ``max_bytes + 1`` so a growing file cannot bypass its cap."""
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ImportLimitError(f"file exceeds the {max_bytes}-byte import limit")
    return data


def read_limited_text(path, encoding: str = "utf-8") -> str:
    return read_limited_bytes(path).decode(encoding)


def validate_text_size(text: str) -> None:
    if len(text) > MAX_IMPORT_CHARS:
        raise ImportLimitError(f"text exceeds the {MAX_IMPORT_CHARS}-character import limit")


def validate_json_value(value) -> None:
    """Bound JSON nesting, node count, and individual strings after decoding."""
    stack = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ImportLimitError(f"JSON exceeds the {MAX_JSON_NODES}-node import limit")
        if depth > MAX_JSON_DEPTH:
            raise ImportLimitError(f"JSON nesting exceeds the {MAX_JSON_DEPTH}-level import limit")
        if isinstance(current, str):
            if len(current) > MAX_FIELD_CHARS:
                raise ImportLimitError(f"JSON string exceeds the {MAX_FIELD_CHARS}-character field limit")
        elif isinstance(current, dict):
            for key, item in current.items():
                stack.append((key, depth + 1))
                stack.append((item, depth + 1))
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
