from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    ENGINE = "engine"
    STORAGE = "storage"
    LLM = "llm"
    AUTH = "auth"
    INTEGRATION = "integration"
    SYSTEM = "system"


class ErrorSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class FinModelError(Exception):
    """Base error class for all FinModel errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[str] = None,
        user_message: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.user_message = user_message or message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "severity": self.severity.value,
            "user_message": self.user_message,
            "timestamp": self.timestamp.isoformat() + "Z",
            "retry_after": self.retry_after,
        }


class ValidationError(FinModelError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            code=kwargs.pop("code", "ERR_VAL_INVALID"),
            message=message,
            category=ErrorCategory.VALIDATION,
            **kwargs,
        )


class EngineError(FinModelError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            code=kwargs.pop("code", "ERR_ENG_EXECUTION_FAILED"),
            message=message,
            category=ErrorCategory.ENGINE,
            **kwargs,
        )


class StorageError(FinModelError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            code=kwargs.pop("code", "ERR_STOR_OPERATION_FAILED"),
            message=message,
            category=ErrorCategory.STORAGE,
            **kwargs,
        )


def get_http_status(error_code: str) -> int:
    if error_code.startswith("ERR_VAL_"):
        return 422
    if error_code.startswith("ERR_AUTH_"):
        return 401 if "INVALID_TOKEN" in error_code else 403
    if error_code.startswith("ERR_STOR_NOT_FOUND"):
        return 404
    if error_code.startswith("ERR_STOR_ALREADY_EXISTS"):
        return 409
    if error_code.startswith("ERR_LLM_RATE_LIMIT") or error_code.startswith("ERR_LLM_QUOTA"):
        return 429
    if error_code.endswith("TIMEOUT"):
        return 504
    if error_code.endswith("UNAVAILABLE"):
        return 503
    return 500
