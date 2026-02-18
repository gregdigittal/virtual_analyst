from __future__ import annotations

import time


class CircuitBreaker:
    """In-memory circuit breaker; dict access is safe under CPython GIL."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: int = 60) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_sec = recovery_timeout_sec
        self._state: dict[str, str] = {}
        self._failure_count: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}

    def is_open(self, provider_key: str) -> bool:
        state = self._state.get(provider_key, "closed")
        if state == "closed":
            return False
        if state == "open":
            if time.monotonic() - self._last_failure_time.get(provider_key, 0) >= self._recovery_timeout_sec:
                self._state[provider_key] = "half_open"
                return False
            return True
        return False

    def record_failure(self, provider_key: str) -> None:
        self._last_failure_time[provider_key] = time.monotonic()
        if self._state.get(provider_key) == "half_open":
            self._state[provider_key] = "open"
            return
        count = self._failure_count.get(provider_key, 0) + 1
        self._failure_count[provider_key] = count
        if count >= self._failure_threshold:
            self._state[provider_key] = "open"

    def record_success(self, provider_key: str) -> None:
        self._state[provider_key] = "closed"
        self._failure_count[provider_key] = 0
