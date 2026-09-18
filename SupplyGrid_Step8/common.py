"""Strict structured handoffs and JSON-safe evidence (no operational writes)."""
import hashlib
import json
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def safe(value):
    if isinstance(value, Decimal):
        return str(value)  # Keep exact monetary amounts, not binary floating point.
    if isinstance(value, (date, datetime, Path)):
        return str(value)
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            return [{"key": safe(k), "value": safe(v)} for k, v in value.items()]
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(v) for v in value]
    if hasattr(value, "item"):
        return safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite output rejected")
    return value


def encoded(value):
    return json.dumps(safe(value), sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(safe(value), indent=2, allow_nan=False).encode())


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_message(role, message, case_id, supplier):
    # JSON Schema is evaluated against the serialized wire representation.
    import jsonschema
    schema = json.loads((ROOT / "schemas" / (role + "_schema.json")).read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(safe(message))
    if message["case_id"] != case_id or message["supplier_id"] != supplier:
        raise ValueError("Cross-case or cross-supplier handoff rejected")
    data = message["data"]
    if role == "risk":
        if data["supplier_id"] != supplier:
            raise ValueError("Risk supplier mismatch")
        expected = "HIGH" if data["disruption_probability"] >= data["threshold"] else "LOW"
        if data["risk_level"] != expected:
            raise ValueError("Risk classification disagrees with frozen threshold")
    if role == "impact" and data["supplier"] != supplier:
        raise ValueError("Impact supplier mismatch")
    if role == "financial":
        for value in data["breakdown"].values():
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Invalid financial amount")
        ids = [v["order_id"] for v in data["detail"]]
        if len(set(ids)) != len(ids) or len(ids) != data["evaluated_orders"]:
            raise ValueError("Financial order counts inconsistent")
    if role == "mitigation":
        ids = [v["action_id"] for v in data["candidates"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate mitigation candidate IDs")
        for candidate in data["candidates"]:
            amount = Decimal(str(candidate["action_cost"]))
            if not amount.is_finite() or amount < 0 or candidate.get("feasible") is not True:
                raise ValueError("Invalid candidate cost/feasibility")
    if role == "optimization":
        if Decimal(str(data["objective_value"])) * 100 != data["audit"]["total_cost_cents"]:
            raise ValueError("Objective differs from independently audited cost")
    return message
