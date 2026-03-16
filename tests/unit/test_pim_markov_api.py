"""PIM-5.4: Markov router API unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-markov-api"

_STATE_ROWS = [
    {
        "state_index": i,
        "gdp_state": i // 27,
        "sentiment_state": (i % 27) // 9,
        "quality_state": (i % 9) // 3,
        "momentum_state": i % 3,
        "label": f"label-{i}",
    }
    for i in range(81)
]

_MATRIX_ROW = {
    "matrix_id": "mat-001",
    "n_observations": 120,
    "is_ergodic": True,
}


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.fixture(autouse=True)
def _bypass_pim_gate():
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


def _uniform_transition_rows() -> list[dict]:
    n = 81
    p = 1.0 / n
    return [
        {"from_state": i, "to_state": j, "probability": p}
        for i in range(n)
        for j in range(n)
    ]


# --- GET /pim/markov/states ---


def test_states_requires_tenant() -> None:
    r = client.get("/api/v1/pim/markov/states")
    assert r.status_code == 400


def test_states_returns_81_labels() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=_STATE_ROWS)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/states", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 81
    assert len(data["items"]) == 81
    assert data["items"][0]["state_index"] == 0
    assert data["items"][0]["label"] == "label-0"


# --- GET /pim/markov/steady-state ---


def test_steady_state_requires_tenant() -> None:
    r = client.get("/api/v1/pim/markov/steady-state")
    assert r.status_code == 400


def test_steady_state_404_when_no_matrix() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 404


def test_steady_state_happy_path() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(return_value=_uniform_transition_rows())
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert "top_states" in data
    assert len(data["top_states"]) <= 10
    assert data["n_observations"] == 120
    assert data["matrix_id"] == "mat-001"
    # Uniform matrix → all probabilities ≈ 1/81
    for s in data["top_states"]:
        assert abs(s["probability"] - 1 / 81) < 0.01


# --- GET /pim/markov/top-transitions ---


def test_top_transitions_requires_tenant() -> None:
    r = client.get("/api/v1/pim/markov/top-transitions")
    assert r.status_code == 400


def test_top_transitions_404_when_no_matrix() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/top-transitions", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 404


def test_top_transitions_uniform_matrix_no_strong_edges() -> None:
    """Uniform matrix: p = 1/81 ≈ 0.012 < 0.05 threshold → no edges returned."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(side_effect=[_uniform_transition_rows(), _STATE_ROWS])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/markov/top-transitions?top_n=5",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["edges"], list)
    assert isinstance(data["top_state_indices"], list)
    assert len(data["top_state_indices"]) == 5
    # No edges because all p ≈ 0.012 < 0.05
    assert len(data["edges"]) == 0


def test_top_transitions_top_n_clamped() -> None:
    """top_n is clamped to [3, 15]."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(side_effect=[_uniform_transition_rows(), _STATE_ROWS])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/markov/top-transitions?top_n=100",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert len(data["top_state_indices"]) <= 15


def test_steady_state_metadata_fields() -> None:
    """Steady-state response includes expected metadata fields."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(return_value=_uniform_transition_rows())
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert "is_ergodic" in data
    assert "n_observations" in data
    assert "matrix_id" in data
    assert data["matrix_id"] == "mat-001"


def test_states_empty_when_no_rows() -> None:
    """Returns empty items list when no state labels have been seeded."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/states", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_top_transitions_default_top_n() -> None:
    """Without explicit top_n the default should be applied without error."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(side_effect=[_uniform_transition_rows(), _STATE_ROWS])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/top-transitions", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert "edges" in data
    assert "top_state_indices" in data


# ---------------------------------------------------------------------------
# SP8-B2: Markov steady-state CI tests
# ---------------------------------------------------------------------------


def test_steady_state_includes_ci_arrays() -> None:
    """Steady-state response includes ci_lower and ci_upper arrays."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(return_value=_uniform_transition_rows())
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert "ci_lower" in data
    assert "ci_upper" in data
    assert data["ci_lower"] is not None
    assert data["ci_upper"] is not None
    assert len(data["ci_lower"]) == 81
    assert len(data["ci_upper"]) == 81


def test_steady_state_ci_bounds_clamped_to_01() -> None:
    """All CI bounds are within [0, 1]."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_MATRIX_ROW)
    conn.fetch = AsyncMock(return_value=_uniform_transition_rows())
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    for lb, ub in zip(data["ci_lower"], data["ci_upper"], strict=False):
        assert 0.0 <= lb <= 1.0, f"ci_lower out of range: {lb}"
        assert 0.0 <= ub <= 1.0, f"ci_upper out of range: {ub}"
        assert lb <= ub, f"ci_lower ({lb}) > ci_upper ({ub})"


def test_steady_state_ci_warning_when_low_observations() -> None:
    """ci_warning is set and CIs are null when n_observations < 10."""
    low_obs_row = {
        "matrix_id": "mat-low",
        "n_observations": 5,
        "is_ergodic": True,
    }
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=low_obs_row)
    conn.fetch = AsyncMock(return_value=_uniform_transition_rows())
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_markov.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/markov/steady-state", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["ci_lower"] is None
    assert data["ci_upper"] is None
    assert "ci_warning" in data
    assert data["ci_warning"] is not None
    assert "n<10" in data["ci_warning"]
