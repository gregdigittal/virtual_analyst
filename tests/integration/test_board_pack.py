"""VA-P7-12: Board pack integration tests — create, list, get, export (generate skipped without LLM)."""

from __future__ import annotations

from tests.integration.conftest import integration_marker


@integration_marker
async def test_board_pack_create_list_get(client) -> None:
    """Create board pack, list, get by id."""
    tenant = "t_integration_boardpack"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": "u1"}
    create = await client.post(
        "/api/v1/board-packs",
        json={"label": "Integration test pack", "run_id": "run_fake_123"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    pack_id = body["pack_id"]
    assert body["label"] == "Integration test pack"
    assert body["run_id"] == "run_fake_123"
    assert body["status"] == "draft"

    list_resp = await client.get("/api/v1/board-packs", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["items"]
    assert any(p["pack_id"] == pack_id for p in items)

    get_resp = await client.get(f"/api/v1/board-packs/{pack_id}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["pack_id"] == pack_id
    assert get_resp.json()["status"] == "draft"
    assert "narrative_json" in get_resp.json()
    assert "section_order" in get_resp.json()


@integration_marker
async def test_board_pack_export_requires_ready(client) -> None:
    """Export returns 400 when pack is not ready."""
    tenant = "t_integration_boardpack"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": "u1"}
    create = await client.post(
        "/api/v1/board-packs",
        json={"label": "Export test pack", "run_id": "run_fake_456"},
        headers=headers,
    )
    assert create.status_code == 201
    pack_id = create.json()["pack_id"]
    export_resp = await client.get(
        f"/api/v1/board-packs/{pack_id}/export?format=html",
        headers=headers,
    )
    assert export_resp.status_code == 400, export_resp.text
    assert "ready" in export_resp.json().get("detail", "").lower() or export_resp.text.lower()
