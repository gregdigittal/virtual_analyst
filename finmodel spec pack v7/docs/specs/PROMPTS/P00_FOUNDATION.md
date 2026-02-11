# Phase 0 Prompt — Foundation & Infrastructure
**Date:** 2026-02-11

## Context
Phase 0 establishes the foundational infrastructure, tooling, and practices that all subsequent phases depend on. This phase ensures developers can work efficiently, code quality is maintained, and operational excellence is built in from day one.

## Pre-requisites
- Read: `CURSOR_MASTER_PROMPT.md` (hard constraints)
- Read: `ERROR_HANDLING_SPEC.md` (error patterns)
- Read: `PERFORMANCE_SPEC.md` (performance targets)
- Read: `OBSERVABILITY_SPEC.md` (logging, metrics, tracing)
- Read: `DEPLOYMENT_SPEC.md` (deployment architecture)
- Read: `SECURITY_SPEC.md` (security requirements)
- Read: `AUDIT_COMPLIANCE_SPEC.md` (audit logging)
- Read: `REPO_SCAFFOLDING_LAYOUT.md` (directory structure)

## Phase 0 Goals
1. **Development environment** — Any developer can run locally in <30 min
2. **CI/CD pipeline** — Automated testing and deployment
3. **Error handling framework** — Consistent error responses
4. **Logging infrastructure** — Structured logs with correlation IDs
5. **Monitoring foundation** — Metrics and health checks
6. **Security hardening** — Input validation, security headers

## Tasks (execute in order)

### 0.1 Repository Setup

```bash
# Initialize monorepo structure
mkdir -p finmodel/{apps,shared,tests,docs,scripts}
mkdir -p finmodel/apps/{api,web,worker}
mkdir -p finmodel/shared/fm_shared/{model,storage,validation,analysis,venture,scenarios,export}
mkdir -p finmodel/tests/{unit,integration,e2e,security,load}
mkdir -p finmodel/docs/{specs,architecture,runbooks}

# Git initialization
cd finmodel
git init
git branch -M main

# .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/

# Node
node_modules/
.next/
out/
*.log

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Test
.coverage
htmlcov/
.pytest_cache/
.tox/

# Secrets
*.pem
*.key
credentials.json
EOF
```

### 0.2 Python Project Setup

```toml
# pyproject.toml
[project]
name = "finmodel"
version = "0.1.0"
description = "Deterministic financial modeling platform with LLM assistance"
requires-python = ">=3.12"

dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "supabase>=2.3.0",
    "redis[hiredis]>=5.0.1",
    "celery>=5.3.4",
    "numpy>=1.26.3",
    "pandas>=2.1.4",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.26.0",
    "structlog>=24.1.0",
    "prometheus-client>=0.19.0",
    "opentelemetry-api>=1.22.0",
    "opentelemetry-sdk>=1.22.0",
    "opentelemetry-instrumentation-fastapi>=0.43b0",
    "tenacity>=8.2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.23.3",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",  # for testing
    "ruff>=0.1.9",
    "black>=23.12.1",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line too long (handled by black)

[tool.black]
line-length = 100
target-version = ['py312']

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --cov=apps --cov=shared --cov-report=html --cov-report=term"
```

### 0.3 Next.js Project Setup

```bash
# Create Next.js app
cd apps/web
npx create-next-app@latest . --typescript --tailwind --app --no-src-dir

# Install dependencies
npm install @supabase/supabase-js @tanstack/react-query zustand react-hook-form zod
npm install -D @types/node typescript
```

```json
// apps/web/package.json additions
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest",
    "test:e2e": "playwright test"
  }
}
```

### 0.4 Docker Compose for Local Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: finmodel_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  supabase:
    image: supabase/supabase-dev:latest
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - "54321:8000"
    volumes:
      - supabase_data:/var/lib/postgresql/data

volumes:
  postgres_data:
  redis_data:
  supabase_data:
```

### 0.5 Environment Configuration

```bash
# .env.example
# Copy to .env and fill in actual values

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finmodel_dev

# Supabase
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Redis
REDIS_URL=redis://localhost:6379

# LLM Providers (leave empty for mock in development)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Security
JWT_SECRET=your-secret-key-change-in-production
ENCRYPTION_KEY=your-encryption-key

# Observability
ENABLE_METRICS=true
ENABLE_TRACING=false  # Disable in dev for simplicity

# API
API_HOST=0.0.0.0
API_PORT=8000

# Web
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### 0.6 Error Handling Framework

```python
# shared/fm_shared/errors.py
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

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
    """Base error class for all FinModel errors"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[str] = None,
        user_message: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
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
            "retry_after": self.retry_after
        }

# Specific error types
class ValidationError(FinModelError):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=kwargs.pop("code", "ERR_VAL_INVALID"),
            message=message,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )

class EngineError(FinModelError):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=kwargs.pop("code", "ERR_ENG_EXECUTION_FAILED"),
            message=message,
            category=ErrorCategory.ENGINE,
            **kwargs
        )

class StorageError(FinModelError):
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=kwargs.pop("code", "ERR_STOR_OPERATION_FAILED"),
            message=message,
            category=ErrorCategory.STORAGE,
            **kwargs
        )

# FastAPI error handlers
# apps/api/app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from shared.fm_shared.errors import FinModelError
import structlog

logger = structlog.get_logger()

@app.exception_handler(FinModelError)
async def finmodel_error_handler(request: Request, exc: FinModelError):
    logger.error(
        "FinModel error",
        error_code=exc.code,
        error_message=exc.message,
        category=exc.category.value,
        severity=exc.severity.value,
        context=exc.context
    )

    return JSONResponse(
        status_code=get_http_status(exc.code),
        content={
            "error": exc.to_dict(),
            "meta": {
                "request_id": request.state.request_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
    )

def get_http_status(error_code: str) -> int:
    """Map error codes to HTTP status codes"""
    if error_code.startswith("ERR_VAL_"):
        return 422
    elif error_code.startswith("ERR_AUTH_"):
        return 401 if "INVALID_TOKEN" in error_code else 403
    elif error_code.startswith("ERR_STOR_NOT_FOUND"):
        return 404
    elif error_code.startswith("ERR_STOR_ALREADY_EXISTS"):
        return 409
    elif error_code.startswith("ERR_LLM_RATE_LIMIT") or error_code.startswith("ERR_LLM_QUOTA"):
        return 429
    elif error_code.endswith("TIMEOUT"):
        return 504
    elif error_code.endswith("UNAVAILABLE"):
        return 503
    else:
        return 500
```

### 0.7 Structured Logging Setup

```python
# shared/fm_shared/logging.py
import structlog
from contextvars import ContextVar
import logging
import sys

# Context variables for correlation
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default=None)
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str] = ContextVar("user_id", default=None)

def configure_logging(environment: str = "development"):
    """Configure structured logging"""

    # Processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if environment == "development":
        # Pretty console output for dev
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON for production (CloudWatch, etc.)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if environment == "production" else logging.DEBUG
    )

# Middleware to bind context
# apps/api/app/main.py
import uuid

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Generate or extract correlation ID
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id_var.set(correlation_id)

    # Bind context
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host
    )

    # Add to request state
    request.state.request_id = correlation_id

    # Process request
    response = await call_next(request)

    # Add correlation ID to response headers
    response.headers["X-Request-ID"] = correlation_id

    return response
```

### 0.8 Metrics & Health Checks

```python
# shared/fm_shared/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info

# API metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"]
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30]
)

api_requests_active = Gauge(
    "api_requests_active",
    "Currently active API requests"
)

# Middleware
# apps/api/app/main.py
import time

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    api_requests_active.inc()
    start = time.time()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        status = 500
        raise
    finally:
        duration = time.time() - start
        api_requests_active.dec()

        api_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=status
        ).inc()

        api_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

    return response

# Expose metrics endpoint
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Health check endpoints
@app.get("/api/v1/health/live")
async def liveness():
    """Liveness probe"""
    return {"status": "ok"}

@app.get("/api/v1/health/ready")
async def readiness():
    """Readiness probe"""
    checks = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Check Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks}
    )
```

### 0.9 Security Middleware

```python
# apps/api/app/middleware/security.py

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    return response

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Input validation (automatic via Pydantic)
# All request bodies must be Pydantic models
```

### 0.10 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.12
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check .

      - name: Format check with black
        run: black --check .

      - name: Type check with mypy
        run: mypy apps/ shared/

      - name: Start services (Postgres, Redis)
        run: docker-compose up -d

      - name: Wait for services
        run: sleep 10

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3

      - name: Security scan (Safety)
        run: safety check --json

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: docker build -t finmodel/api:${{ github.sha }} .

      - name: Scan image for vulnerabilities
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy image finmodel/api:${{ github.sha }}
```

### 0.11 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [ --fix ]

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key

# Install hooks
# pre-commit install
```

### 0.12 FastAPI Application Skeleton

```python
# apps/api/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.fm_shared.logging import configure_logging
from shared.fm_shared.metrics import metrics_app
import os

# Configure logging
configure_logging(environment=os.getenv("ENVIRONMENT", "development"))

# Create app
app = FastAPI(
    title="FinModel API",
    version="0.1.0",
    description="Deterministic financial modeling platform"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware (order matters!)
from apps.api.app.middleware.logging import logging_middleware
from apps.api.app.middleware.security import security_headers
from apps.api.app.middleware.metrics import metrics_middleware

app.middleware("http")(logging_middleware)
app.middleware("http")(security_headers)
app.middleware("http")(metrics_middleware)

# Error handlers
from shared.fm_shared.errors import FinModelError, finmodel_error_handler
app.add_exception_handler(FinModelError, finmodel_error_handler)

# Routes
from apps.api.app.routers import health

app.include_router(health.router, prefix="/api/v1", tags=["health"])

# Metrics endpoint
app.mount("/metrics", metrics_app)

# Root
@app.get("/")
async def root():
    return {"name": "FinModel API", "version": "0.1.0", "status": "ok"}
```

---

## Gate Criteria

- [ ] Repository structure created and initialized
- [ ] Docker Compose starts all services (Postgres, Redis, Supabase)
- [ ] Any developer can run `docker-compose up && pip install -e ".[dev]"` and have working environment
- [ ] FastAPI app starts and responds to health checks
- [ ] Structured logs output correctly (JSON in prod, pretty in dev)
- [ ] Metrics endpoint `/metrics` returns Prometheus format
- [ ] Error handling returns consistent error envelope
- [ ] Pre-commit hooks run and pass
- [ ] CI pipeline runs and passes (lint, type check, unit tests)
- [ ] Security headers present in API responses
- [ ] Rate limiting functional (test with `curl`)
- [ ] Documentation: README.md with setup instructions

---

## Deliverables

1. **Working development environment**
   - Docker Compose configuration
   - `.env.example` with all required variables
   - README.md with setup instructions

2. **Python project scaffolding**
   - `pyproject.toml` with dependencies
   - Monorepo structure (apps, shared, tests)
   - Error handling framework
   - Structured logging

3. **FastAPI application skeleton**
   - Health check endpoints
   - Metrics endpoint
   - Security middleware
   - Error handlers
   - CORS configuration

4. **CI/CD pipeline**
   - GitHub Actions workflow
   - Automated tests
   - Linting and type checking
   - Security scanning

5. **Development tooling**
   - Pre-commit hooks
   - Ruff + Black configuration
   - MyPy type checking
   - Pytest configuration

---

## Next Steps

After Phase 0 gate passes:
- Proceed to **Phase 1**: Core Model Engine
- All infrastructure is in place
- Developers can focus on business logic
- Quality and security are enforced automatically
