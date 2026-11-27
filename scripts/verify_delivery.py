"""Validate the actual result against the case contract before final delivery."""

import argparse
import json
import math
from pathlib import Path


def load(path):
    return path.read_text(encoding="utf-8-sig")


def read(path):
    return json.loads(load(path))


def schema_for(contract):
    if isinstance(contract, list):
        fields = {}
        required = []
        for item in contract:
            if isinstance(item, str):
                name, spec = item, {}
            else:
                name = item.get("name") or item.get("field")
                spec = item
            if not isinstance(name, str) or not name:
                raise ValueError("Invalid field in output_contract")
            fields[name] = spec
            if spec.get("required", True):
                required.append(name)
        return {"type": "object", "properties": fields, "required": required}
    if not isinstance(contract, dict):
        raise ValueError("output_contract must be a list or an object")
    if "fields" in contract:
        schema = schema_for(contract["fields"])
        return {**schema, "required": contract.get("required", schema["required"])}
    if "properties" in contract or "required" in contract:
        return {"type": "object", **contract}
    return {"type": "object", "properties": contract, "required": list(contract)}


TYPES = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "number": lambda value: type(value) in (float, int) and math.isfinite(value),
    "integer": lambda value: type(value) is int,
    "boolean": lambda value: type(value) is bool,
    "null": lambda value: value is None,
}


def errors_for(value, schema, label):
    if not isinstance(schema, dict):
        return
    declared = schema.get("type")
    alternatives = declared if isinstance(declared, list) else [declared]
    known_types = [kind for kind in alternatives if kind in TYPES]
    if known_types and not any(TYPES[kind](value) for kind in known_types):
        yield f"{label}: expected {declared}"
        return
    if "enum" in schema and value not in schema["enum"]:
        yield f"{label}: value is outside the allowed options"
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for field in schema.get("required", []) or []:
            if field not in value or (value[field] is None and not allows_null(properties.get(field))):
                yield f"{label}.{field}: missing required value"
        for field, item in value.items():
            if field in properties:
                yield from errors_for(item, properties[field], f"{label}.{field}")
            elif schema.get("additionalProperties") is False:
                yield f"{label}.{field}: unexpected field"
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            yield f"{label}: fewer items than required"
        for i, item in enumerate(value):
            yield from errors_for(item, schema.get("items", {}), f"{label}[{i}]")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        yield f"{label}: text is shorter than required"


def allows_null(schema):
    kind = schema.get("type") if isinstance(schema, dict) else None
    return kind == "null" or (isinstance(kind, list) and "null" in kind)


def validate(case, result, root, artifacts):
    schema = schema_for(case.get("output_contract", {}))
    if schema.get("additionalProperties") is False and "case_id" not in schema.get("properties", {}):
        schema["properties"] = {**schema.get("properties", {}), "case_id": {}}
    errors = list(errors_for(result, schema, "result"))
    if case.get("case_id") is None or result.get("case_id") != case.get("case_id"):
        errors.append("result.case_id must equal the original case_id")
    for name in dict.fromkeys(artifacts):
        file = (root / name).resolve()
        if Path(name).is_absolute() or not file.is_relative_to(root):
            errors.append(f"{name}: expected an output-relative artifact path")
        elif not file.is_file() or not file.stat().st_size:
            errors.append(f"{name}: missing or empty artifact")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    errors = validate(read(args.case), read(args.result), args.result.resolve().parent, args.artifact)
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=True))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
