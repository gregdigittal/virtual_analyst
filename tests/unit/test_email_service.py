"""H-03: Unit tests for the email service (SendGrid board pack distribution)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.email import (
    EmailError,
    _build_html,
    _build_plain,
    _format_narrative,
    send_board_pack_email,
)


# ---------------------------------------------------------------------------
# _format_narrative
# ---------------------------------------------------------------------------

def test_format_narrative_none() -> None:
    result = _format_narrative(None)
    assert "executive_summary" in result


def test_format_narrative_dict() -> None:
    result = _format_narrative({"exec": "Good quarter", "outlook": "Positive"})
    assert result == {"exec": "Good quarter", "outlook": "Positive"}


def test_format_narrative_json_string() -> None:
    result = _format_narrative('{"exec": "Revenue up"}')
    assert result == {"exec": "Revenue up"}


def test_format_narrative_plain_string() -> None:
    result = _format_narrative("Just a plain summary")
    assert result == {"executive_summary": "Just a plain summary"}


# ---------------------------------------------------------------------------
# _build_html / _build_plain
# ---------------------------------------------------------------------------

def test_build_html_escapes_content() -> None:
    html = _build_html("Q1 <Pack>", {"summary": "Revenue > $1M & growing"})
    assert "&lt;Pack&gt;" in html
    assert "&gt; $1M &amp; growing" in html
    assert "<h2" in html


def test_build_plain_includes_sections() -> None:
    plain = _build_plain("Q1 Pack", {"exec_summary": "Good", "outlook": "Stable"})
    assert "Q1 Pack" in plain
    assert "Exec Summary" in plain
    assert "Good" in plain
    assert "Outlook" in plain


# ---------------------------------------------------------------------------
# send_board_pack_email
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_skips_when_no_api_key() -> None:
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = None

    with patch("apps.api.app.services.email.get_settings", return_value=mock_settings):
        result = await send_board_pack_email(
            ["cfo@example.com"],
            "Q1 Pack",
            {"executive_summary": "Good quarter."},
        )
    assert result["sent"] is False
    assert result["reason"] == "sendgrid_not_configured"


@pytest.mark.asyncio
async def test_send_skips_when_no_recipients() -> None:
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test_key"

    with patch("apps.api.app.services.email.get_settings", return_value=mock_settings):
        result = await send_board_pack_email([], "Q1 Pack", None)
    assert result["sent"] is False
    assert result["reason"] == "no_recipients"


@pytest.mark.asyncio
async def test_send_no_recipients_takes_precedence_over_no_api_key() -> None:
    """Empty recipients should return no_recipients even without an API key."""
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = None

    with patch("apps.api.app.services.email.get_settings", return_value=mock_settings):
        result = await send_board_pack_email([], "Q1 Pack", None)
    assert result["sent"] is False
    assert result["reason"] == "no_recipients"


@pytest.mark.asyncio
async def test_send_success_via_sendgrid() -> None:
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test_key"
    mock_settings.email_from_address = "noreply@test.com"
    mock_settings.email_from_name = "Test"

    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("apps.api.app.services.email.get_settings", return_value=mock_settings),
        patch("apps.api.app.services.email.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await send_board_pack_email(
            ["cfo@example.com", "cto@example.com"],
            "Q1 Pack",
            {"executive_summary": "Revenue up 15%."},
        )

    assert result["sent"] is True
    assert result["recipients"] == ["cfo@example.com", "cto@example.com"]

    # Verify the SendGrid API was called correctly
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "https://api.sendgrid.com/v3/mail/send"
    payload = call_args[1]["json"]
    assert payload["subject"] == "Board Pack: Q1 Pack"
    assert payload["from"]["email"] == "noreply@test.com"
    assert len(payload["personalizations"][0]["to"]) == 2


@pytest.mark.asyncio
async def test_send_raises_on_sendgrid_error() -> None:
    mock_settings = MagicMock()
    mock_settings.sendgrid_api_key = "SG.test_key"
    mock_settings.email_from_address = "noreply@test.com"
    mock_settings.email_from_name = "Test"

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("apps.api.app.services.email.get_settings", return_value=mock_settings),
        patch("apps.api.app.services.email.httpx.AsyncClient", return_value=mock_client),
    ):
        with pytest.raises(EmailError, match="403"):
            await send_board_pack_email(
                ["cfo@example.com"],
                "Q1 Pack",
                {"executive_summary": "Good."},
            )
