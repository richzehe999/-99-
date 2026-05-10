"""
Small PyYAML-compatible fallback for the bundled example configs.

It implements only the subset used by config.enhanced.yaml so the examples can
run in offline environments where PyYAML cannot be installed.
"""
from __future__ import annotations

import ast
from typing import Any


def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    for i, ch in enumerate(line):
        if ch in {"'", '"'}:
            in_quote = None if in_quote == ch else ch
        elif ch == "#" and in_quote is None:
            return line[:i]
    return line


def _scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return ast.literal_eval(value)
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def safe_load(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_item: dict[str, Any] | None = None
    current_list: list[Any] | None = None

    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0 and stripped.endswith(":"):
            current_key = stripped[:-1]
            data[current_key] = None
            current_item = None
            current_list = None
            continue

        if indent == 0 and ":" in stripped:
            key, value = stripped.split(":", 1)
            data[key.strip()] = _scalar(value)
            current_key = key.strip()
            current_item = None
            current_list = None
            continue

        if current_key is None:
            continue

        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if current_list is None:
                if data[current_key] is None:
                    data[current_key] = []
                    current_list = data[current_key]
                elif isinstance(data[current_key], list):
                    current_list = data[current_key]
                else:
                    continue
            if ":" in value:
                key, raw_value = value.split(":", 1)
                current_item = {key.strip(): _scalar(raw_value)}
                current_list.append(current_item)
            else:
                current_item = None
                current_list.append(_scalar(value))
            continue

        if ":" in stripped:
            key, value = stripped.split(":", 1)
            target: dict[str, Any]
            if isinstance(data[current_key], list) and current_item is not None:
                target = current_item
            else:
                if data[current_key] is None:
                    data[current_key] = {}
                target = data[current_key]
            parsed = _scalar(value)
            if value.strip() == "":
                parsed = []
                current_list = parsed
            else:
                current_list = None
            target[key.strip()] = parsed

    return data
