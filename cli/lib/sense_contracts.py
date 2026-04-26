"""User-defined contracts for Aura sense output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib import state


META_KEYS = {"name", "description", "instructions", "fields", "required"}


def load_contract(spec: str | None) -> dict[str, Any] | None:
    """Load a sense contract from inline JSON, @file, path, or state name."""
    if not spec:
        return None
    raw = _read_contract_text(spec)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid sense contract JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("sense contract must be a JSON object")
    return normalize_contract(value, source=_source_label(spec))


def normalize_contract(value: dict[str, Any], *, source: str | None = None) -> dict[str, Any]:
    fields_value = value.get("fields")
    if fields_value is None:
        fields_value = {key: field for key, field in value.items() if key not in META_KEYS}
    if not isinstance(fields_value, dict) or not fields_value:
        raise ValueError("sense contract requires a non-empty fields object")

    required_raw = value.get("required", [])
    if isinstance(required_raw, str):
        required = {required_raw}
    elif isinstance(required_raw, list):
        required = {str(item) for item in required_raw}
    else:
        required = set()

    fields: dict[str, dict[str, Any]] = {}
    for name, spec in fields_value.items():
        field_name = str(name).strip()
        if not field_name:
            continue
        field = _normalize_field(spec)
        if field.get("required") is True:
            required.add(field_name)
        field["required"] = field_name in required
        fields[field_name] = field
    if not fields:
        raise ValueError("sense contract did not define any valid fields")

    return {
        "name": value.get("name"),
        "description": value.get("description"),
        "instructions": value.get("instructions"),
        "source": source,
        "fields": fields,
        "required": sorted(required.intersection(fields)),
    }


def coerce_contract_result(contract: dict[str, Any] | None, value: Any) -> dict[str, Any] | None:
    """Coerce an LLM-produced contract payload into the requested field shape."""
    if not contract:
        return None
    raw = value if isinstance(value, dict) else {}
    out: dict[str, Any] = {}
    for name, field in contract.get("fields", {}).items():
        out[name] = _coerce_value(raw.get(name), field)
    return out


def prompt_contract(contract: dict[str, Any] | None) -> str:
    if not contract:
        return "No custom contract requested."
    prompt_value = {
        "name": contract.get("name"),
        "description": contract.get("description"),
        "instructions": contract.get("instructions"),
        "required": contract.get("required", []),
        "fields": contract.get("fields", {}),
    }
    return json.dumps(prompt_value, indent=2, sort_keys=True)


def _read_contract_text(spec: str) -> str:
    text = spec.strip()
    if text.startswith("@"):
        return Path(text[1:]).read_text(encoding="utf-8")
    if text.startswith("{"):
        return text

    path = Path(text)
    if path.exists():
        return path.read_text(encoding="utf-8")

    name = text[:-5] if text.endswith(".json") else text
    named_path = state.state_root() / "contracts" / "sense" / f"{name}.json"
    if named_path.exists():
        return named_path.read_text(encoding="utf-8")
    raise ValueError(f"sense contract not found: {spec}")


def _source_label(spec: str) -> str:
    text = spec.strip()
    if text.startswith("@"):
        return text
    if text.startswith("{"):
        return "inline"
    path = Path(text)
    if path.exists():
        return str(path)
    return text[:-5] if text.endswith(".json") else text


def _normalize_field(spec: Any) -> dict[str, Any]:
    if isinstance(spec, str):
        return {"type": spec}
    if isinstance(spec, dict):
        field = dict(spec)
        field.setdefault("type", "any")
        return field
    if isinstance(spec, list):
        return {"type": spec}
    return {"type": "any", "description": str(spec)}


def _coerce_value(value: Any, field: dict[str, Any]) -> Any:
    types = _field_types(field.get("type", "any"))
    nullable = "null" in types or field.get("nullable") is True
    if value is None:
        return None if nullable or not field.get("required") else _default_for(types)

    primary = next((item for item in types if item != "null"), "any")
    if primary in {"any", "json"}:
        return value
    if primary in {"string", "str"}:
        return str(value)
    if primary in {"boolean", "bool"}:
        return _coerce_bool(value)
    if primary in {"integer", "int"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None if nullable else 0
    if primary in {"number", "float"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None if nullable else 0.0
    if primary in {"array", "list"}:
        return value if isinstance(value, list) else [value]
    if primary == "object":
        return value if isinstance(value, dict) else {}
    return value


def _field_types(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip().lower() for part in value.split("|") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip().lower() for part in value if str(part).strip()]
    return ["any"]


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    return None


def _default_for(types: list[str]) -> Any:
    primary = next((item for item in types if item != "null"), "any")
    if primary in {"string", "str"}:
        return ""
    if primary in {"boolean", "bool"}:
        return False
    if primary in {"integer", "int"}:
        return 0
    if primary in {"number", "float"}:
        return 0.0
    if primary in {"array", "list"}:
        return []
    if primary == "object":
        return {}
    return None
