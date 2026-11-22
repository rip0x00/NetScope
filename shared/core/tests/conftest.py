"""Shared fixtures: the JSON Schemas from shared/schemas/ and a
referencing registry so the report schema's $ref to the result schema
resolves offline."""

import json
from pathlib import Path

import pytest
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def result_schema() -> dict:
    return _load("diagnostic-result.schema.json")


@pytest.fixture(scope="session")
def report_schema() -> dict:
    return _load("report.schema.json")


@pytest.fixture(scope="session")
def schema_registry(result_schema, report_schema) -> Registry:
    result_resource = Resource.from_contents(result_schema)
    report_resource = Resource.from_contents(report_schema)
    return Registry().with_resources(
        [
            ("diagnostic-result.schema.json", result_resource),
            (result_schema["$id"], result_resource),
            ("report.schema.json", report_resource),
            (report_schema["$id"], report_resource),
        ]
    )
