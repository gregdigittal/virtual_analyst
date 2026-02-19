"""Unit tests for circuit_breaker.py — in-memory circuit breaker state transitions."""

from __future__ import annotations

import time
from unittest.mock import patch

from apps.api.app.services.llm.circuit_breaker import CircuitBreaker


def test_initial_state_is_closed() -> None:
    """New breaker should be closed (not open) for any provider."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=10)
    assert cb.is_open("openai") is False


def test_opens_after_threshold_failures() -> None:
    """After failure_threshold failures, breaker should open."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=10)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is False  # Only 2 failures
    cb.record_failure("openai")
    assert cb.is_open("openai") is True   # 3rd failure trips it


def test_success_resets_to_closed() -> None:
    """record_success should reset the breaker to closed."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=10)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    cb.record_success("openai")
    assert cb.is_open("openai") is False


def test_half_open_after_timeout() -> None:
    """After recovery_timeout_sec, breaker transitions to half_open (is_open returns False)."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=1)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True

    with patch.object(time, "monotonic", return_value=time.monotonic() + 2):
        assert cb.is_open("openai") is False  # half_open


def test_half_open_failure_reopens() -> None:
    """Failure during half_open should immediately reopen the breaker."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=1)
    cb.record_failure("openai")
    cb.record_failure("openai")

    with patch.object(time, "monotonic", return_value=time.monotonic() + 2):
        assert cb.is_open("openai") is False  # now half_open

    cb.record_failure("openai")
    assert cb.is_open("openai") is True  # re-opened


def test_independent_providers() -> None:
    """Each provider has independent failure counts."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=10)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    assert cb.is_open("anthropic") is False
