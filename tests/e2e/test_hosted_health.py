import os

import httpx
import pytest

HOSTED_API_URL = os.getenv("HOSTED_API_URL", "").rstrip("/")
HOSTED_WEB_URL = os.getenv("HOSTED_WEB_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not HOSTED_API_URL, reason="HOSTED_API_URL must be set to run hosted tests."
)


def test_hosted_api_liveness() -> None:
    response = httpx.get(f"{HOSTED_API_URL}/api/v1/health/live", timeout=10)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_hosted_api_readiness() -> None:
    response = httpx.get(f"{HOSTED_API_URL}/api/v1/health/ready", timeout=10)
    assert response.status_code in (200, 503)


@pytest.mark.skipif(not HOSTED_WEB_URL, reason="HOSTED_WEB_URL not set.")
def test_hosted_web_root() -> None:
    response = httpx.get(HOSTED_WEB_URL, timeout=10)
    assert response.status_code == 200
