# Spec Index v2 (Production-Ready)
**Date:** 2026-02-11

## Core Planning Docs
- **BUILD_PLAN.md** — 6-phase build plan (with Phase 0 Foundation)
- **BACKLOG.md** — All 118 work items with acceptance criteria
- CURSOR_MASTER_PROMPT.md — Master prompt, hard constraints, architecture

## New Foundation Specs (Phase 0)
- **ERROR_HANDLING_SPEC.md** — Error taxonomy, handling patterns, retry strategies
- **PERFORMANCE_SPEC.md** — Performance targets, optimization strategies, scaling
- **OBSERVABILITY_SPEC.md** — Logging, metrics, tracing, monitoring, alerting
- **DEPLOYMENT_SPEC.md** — Infrastructure, CI/CD, secrets, DR, scaling
- **AUDIT_COMPLIANCE_SPEC.md** — Audit logging, SOC 2, GDPR, compliance reporting
- **SECURITY_SPEC.md** — Security controls, threat model, testing

## Architecture Specs
- DRAFT_COMMIT_SPEC.md — Draft → Commit compiler boundary
- RUNTIME_ENGINE_SPEC.md — Deterministic calculation engine
- LLM_INTEGRATION_SPEC.md — LLM provider abstraction + sandbox
- AUTH_AND_TENANCY.md — Auth, RLS, role-permission matrix
- FRONTEND_STACK.md — Frontend framework + key components
- TESTING_STRATEGY.md — Test approach + required coverage

## Reference
- REPO_SCAFFOLDING_LAYOUT.md — Directory structure
- NOTE_ON_SCHEMAS.md — Schema design patterns
- EXCEL_LIVE_LINKS.md — Excel bidirectional sync overview
- CHAT_PACK_SUMMARY.md — Version history

## Schemas
- ARTIFACT_SCHEMAS/*.json — All artifact JSON Schemas (15 total)
- ARTIFACT_EXAMPLES/*.json — Example artifact instances
- TEMPLATES/default_catalog.json — Venture template catalog

## Phase Prompts
- **PROMPTS/P00_FOUNDATION.md** — Phase 0: Foundation & Infrastructure (NEW)
- PROMPTS/P01_CORE_ENGINE.md — Phase 1: Core Model Engine
- PROMPTS/P02_DRAFT_LLM.md — Phase 2: Draft Layer + LLM
- PROMPTS/P03_MC_SCENARIOS_VALUATION.md — Phase 3: Monte Carlo + Valuation
- PROMPTS/P04_ERP_BILLING.md — Phase 4: ERP + Billing
- PROMPTS/P05_EXCEL_MEMOS.md — Phase 5: Excel + Memos

## Marketing
- docs/marketing/POSITIONING.md
- docs/marketing/PRICING_AND_GTM.md
- docs/marketing/PRICING_CALCULATOR_SPEC.md

## Database Migrations
- apps/api/app/db/migrations/0001_init.sql
- apps/api/app/db/migrations/0002_functions_and_rls.sql
- apps/api/app/db/migrations/0003_scenarios.sql
- apps/api/app/db/migrations/0004_integrations_billing_llm.sql
- apps/api/app/db/migrations/0005_excel_and_memos.sql

---

## What's New in v2

### New Specifications (6)
1. **ERROR_HANDLING_SPEC.md** — Complete error handling strategy with error codes, retry logic, circuit breakers
2. **PERFORMANCE_SPEC.md** — SLAs, caching, connection pooling, horizontal scaling
3. **OBSERVABILITY_SPEC.md** — Structured logging, Prometheus metrics, OpenTelemetry tracing, alerting
4. **DEPLOYMENT_SPEC.md** — Docker/K8s deployment, CI/CD pipelines, secrets management, DR procedures
5. **AUDIT_COMPLIANCE_SPEC.md** — Immutable audit logs, SOC 2 readiness, GDPR compliance
6. **SECURITY_SPEC.md** — Threat model, input validation, encryption, LLM security, OWASP Top 10

### Enhanced Build Plan
- **Phase 0 (NEW):** Foundation & Infrastructure (1-2 weeks)
  - Dev environment, CI/CD, error handling, logging, metrics, security middleware
- **Phase 1 (Enhanced):** Added performance monitoring, audit logging, database optimization
- **Phase 2 (Enhanced):** Added background jobs, LLM quality metrics, circuit breakers, notifications
- **Phase 3 (Enhanced):** Added async MC execution, sensitivity analysis, baseline comparison, waterfall charts
- **Phase 4 (Enhanced):** Added complete audit logging, compliance reporting, GDPR endpoints, covenant monitoring, CSV import
- **Phase 5 (Enhanced):** Added PDF upload/OCR, document management, comments, activity feed

### Work Item Count
- **Original:** ~60 items
- **Revised:** 118 items (nearly 2x for production-readiness)
- Includes all infrastructure, security, observability, and compliance requirements

### Timeline Impact
- **Original estimate:** ~15-18 weeks
- **Revised estimate:** ~24-30 weeks (~6-7 months) with 3-4 developers
- Realistic for production-ready v1 with SOC 2 readiness, GDPR compliance, and enterprise features

---

## Quick Start

### For Developers
1. Read **BUILD_PLAN.md** — understand the phased approach
2. Read **BACKLOG.md** — see all work items
3. Start with **PROMPTS/P00_FOUNDATION.md** — set up development environment
4. Follow each phase prompt in order

### For Product/Business
1. Read **BUILD_PLAN.md** — timeline and deliverables
2. Read **PRICING_AND_GTM.md** — go-to-market strategy
3. Read **AUDIT_COMPLIANCE_SPEC.md** — compliance readiness

### For Security/Compliance
1. Read **SECURITY_SPEC.md** — security controls
2. Read **AUDIT_COMPLIANCE_SPEC.md** — audit logging and compliance
3. Read **DEPLOYMENT_SPEC.md** — infrastructure security

### For Operations/DevOps
1. Read **DEPLOYMENT_SPEC.md** — deployment architecture
2. Read **OBSERVABILITY_SPEC.md** — monitoring and alerting
3. Read **PERFORMANCE_SPEC.md** — scaling strategies
