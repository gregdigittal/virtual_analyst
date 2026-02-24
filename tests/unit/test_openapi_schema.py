"""N-05: OpenAPI schema validation tests — verify schema completeness and consistency."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)

# Router prefixes that MUST appear in the schema (one per include_router call).
EXPECTED_PREFIXES = [
    "/api/v1/activity",
    "/api/v1/assignments",
    "/api/v1/audit",
    "/api/v1/auth/saml",
    "/api/v1/baselines",
    "/api/v1/benchmark",
    "/api/v1/billing",
    "/api/v1/board-packs",
    "/api/v1/budgets",
    "/api/v1/changesets",
    "/api/v1/comments",
    "/api/v1/compliance",
    "/api/v1/connectors",
    "/api/v1/covenants",
    "/api/v1/currency",
    "/api/v1/documents",
    "/api/v1/drafts",
    "/api/v1/excel",
    "/api/v1/excel-ingestion",
    "/api/v1/feedback",
    "/api/v1/health",
    "/api/v1/import",
    "/api/v1/integrations",
    "/api/v1/jobs",
    "/api/v1/marketplace",
    "/api/v1/memos",
    "/api/v1/metrics",
    "/api/v1/notifications",
    "/api/v1/org-structures",
    "/api/v1/runs",
    "/api/v1/scenarios",
    "/api/v1/teams",
    "/api/v1/ventures",
    "/api/v1/workflows",
]


def _get_schema() -> dict:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    return r.json()


def test_openapi_schema_valid_structure() -> None:
    """Schema must be well-formed OpenAPI 3.x with required top-level keys."""
    schema = _get_schema()
    assert schema["openapi"].startswith("3.")
    assert "info" in schema
    assert schema["info"]["title"] == "Virtual Analyst API"
    assert "paths" in schema
    assert len(schema["paths"]) > 0


def test_all_routers_documented() -> None:
    """Every mounted router must have at least one path in the schema."""
    schema = _get_schema()
    paths = list(schema["paths"].keys())
    missing = []
    for prefix in EXPECTED_PREFIXES:
        if not any(p.startswith(prefix) for p in paths):
            missing.append(prefix)
    assert not missing, f"Routers missing from OpenAPI schema: {missing}"


def test_no_undocumented_api_routes() -> None:
    """Every /api/v1 route on the app must appear in the OpenAPI schema."""
    schema = _get_schema()
    schema_paths = set(schema["paths"].keys())

    app_paths = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/v1/"):
            app_paths.add(path)

    undocumented = app_paths - schema_paths
    assert not undocumented, f"Routes not in OpenAPI schema: {undocumented}"


def test_all_paths_have_methods() -> None:
    """Every path in the schema must define at least one HTTP method."""
    schema = _get_schema()
    http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    empty = []
    for path, operations in schema["paths"].items():
        methods = set(operations.keys()) & http_methods
        if not methods:
            empty.append(path)
    assert not empty, f"Paths with no HTTP methods: {empty}"


def test_all_operations_have_responses() -> None:
    """Every operation must define at least one response."""
    schema = _get_schema()
    http_methods = {"get", "post", "put", "patch", "delete"}
    missing = []
    for path, operations in schema["paths"].items():
        for method, detail in operations.items():
            if method not in http_methods:
                continue
            if not isinstance(detail, dict):
                continue
            if "responses" not in detail or not detail["responses"]:
                missing.append(f"{method.upper()} {path}")
    assert not missing, f"Operations missing responses: {missing}"


def test_path_count_sanity() -> None:
    """Schema should have a reasonable number of paths (catches import regressions)."""
    schema = _get_schema()
    path_count = len(schema["paths"])
    # We have 146 paths currently; fail if it drops significantly
    assert path_count >= 100, f"Only {path_count} paths — router may be missing"
