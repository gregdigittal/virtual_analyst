# Audit & Compliance Specification
**Date:** 2026-02-11

## Overview
FinModel implements comprehensive audit logging and compliance controls to meet SOC 2, GDPR, and financial services regulatory requirements. All data access, modifications, and exports are tracked and auditable.

## Audit Event Catalog

### Event Types

| Event Type | Category | Retention | Description |
|---|---|---|---|
| `user.login` | Authentication | 1 year | User login (success/failure) |
| `user.logout` | Authentication | 1 year | User logout |
| `user.created` | User Management | 7 years | User account created |
| `user.deleted` | User Management | 7 years | User account deleted |
| `user.role_changed` | User Management | 7 years | User role modified |
| `baseline.created` | Data | 7 years | Baseline committed |
| `baseline.updated` | Data | 7 years | Baseline archived/restored |
| `baseline.accessed` | Access | 90 days | Baseline viewed |
| `draft.created` | Data | 7 years | Draft session created |
| `draft.committed` | Data | 7 years | Draft committed to baseline |
| `run.created` | Compute | 1 year | Run executed |
| `run.accessed` | Access | 90 days | Run results viewed |
| `llm.call` | LLM | 1 year | LLM API call made |
| `integration.connected` | Integration | 7 years | ERP integration connected |
| `integration.sync` | Integration | 1 year | ERP sync executed |
| `data.exported` | Export | 7 years | Data exported (Excel, PDF, API) |
| `billing.subscription_changed` | Billing | 7 years | Subscription tier changed |
| `admin.settings_changed` | Admin | 7 years | Tenant settings modified |
| `security.failed_login` | Security | 2 years | Failed login attempt |
| `security.permission_denied` | Security | 2 years | Permission denied |

### Audit Log Schema

```json
{
  "audit_event_id": "ae_abc123",
  "tenant_id": "t_001",
  "user_id": "u_042",
  "event_type": "baseline.created",
  "event_category": "data",
  "timestamp": "2026-02-11T10:30:45.123Z",
  "ip_address": "203.0.113.42",
  "user_agent": "Mozilla/5.0...",
  "session_id": "sess_xyz",
  "correlation_id": "req_abc123",

  "resource": {
    "type": "baseline",
    "id": "bl_001",
    "version": "v1"
  },

  "action": {
    "operation": "create",
    "method": "POST",
    "endpoint": "/api/v1/drafts/ds_001/commit",
    "status": "success"
  },

  "context": {
    "draft_session_id": "ds_001",
    "template_id": "manufacturing_discrete",
    "integrity_status": "warnings_acknowledged"
  },

  "changes": {
    "before": null,
    "after": {
      "baseline_id": "bl_001",
      "status": "active",
      "created_at": "2026-02-11T10:30:45Z"
    }
  },

  "metadata": {
    "source": "web_app",
    "environment": "production"
  }
}
```

### Immutable Audit Log Storage

Audit logs must be **append-only** and **tamper-proof**:

**Implementation Options:**

1. **Dedicated Audit Database Table**
```sql
CREATE TABLE audit_log (
  audit_event_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT,
  event_type TEXT NOT NULL,
  event_category TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_data JSONB NOT NULL,
  checksum TEXT NOT NULL,  -- SHA256 hash for integrity
  -- No UPDATE or DELETE allowed (enforced via RLS + triggers)
  CONSTRAINT no_update CHECK (false)  -- Prevents updates
);

-- Only allow INSERT
CREATE POLICY audit_log_insert ON audit_log
  FOR INSERT WITH CHECK (true);

-- No UPDATE or DELETE policies = no updates/deletes possible

-- Index for querying
CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, timestamp DESC);
CREATE INDEX idx_audit_user_time ON audit_log(user_id, timestamp DESC);
CREATE INDEX idx_audit_event_type ON audit_log(event_type, timestamp DESC);
```

2. **Write to Immutable Storage**
```python
# Also write to S3 with Object Lock (WORM - Write Once Read Many)
async def create_audit_event(event: AuditEvent):
    # Write to database
    await db.execute(insert(audit_log).values(event.dict()))

    # Also write to immutable S3 bucket
    s3_key = f"audit/{event.tenant_id}/{event.timestamp.date()}/{event.audit_event_id}.json"
    await s3_client.put_object(
        Bucket='finmodel-audit-logs',
        Key=s3_key,
        Body=json.dumps(event.dict()),
        # Object Lock prevents deletion for retention period
        ObjectLockMode='GOVERNANCE',
        ObjectLockRetainUntilDate=event.timestamp + timedelta(days=2555)  # 7 years
    )
```

### Audit Event Creation

```python
from contextvars import ContextVar

# Context variables (set by middleware)
current_user_id: ContextVar[str] = ContextVar("user_id")
current_tenant_id: ContextVar[str] = ContextVar("tenant_id")
current_ip: ContextVar[str] = ContextVar("ip_address")

async def create_audit_event(
    event_type: str,
    event_category: str,
    resource_type: str,
    resource_id: str,
    operation: str,
    status: str,
    context: dict = None,
    changes: dict = None
):
    event = AuditEvent(
        audit_event_id=generate_id("ae_"),
        tenant_id=current_tenant_id.get(),
        user_id=current_user_id.get(),
        event_type=event_type,
        event_category=event_category,
        timestamp=datetime.utcnow(),
        ip_address=current_ip.get(),
        resource={"type": resource_type, "id": resource_id},
        action={"operation": operation, "status": status},
        context=context or {},
        changes=changes
    )

    # Compute checksum for integrity
    event.checksum = hashlib.sha256(
        json.dumps(event.dict(), sort_keys=True).encode()
    ).hexdigest()

    await write_audit_event(event)

# Usage
@router.post("/api/v1/drafts/{id}/commit")
async def commit_draft(id: str):
    draft = await get_draft(id)

    # Before commit
    await create_audit_event(
        event_type="draft.committed",
        event_category="data",
        resource_type="baseline",
        resource_id=baseline.baseline_id,
        operation="create",
        status="success",
        context={"draft_session_id": id},
        changes={"before": None, "after": baseline.dict()}
    )

    # Commit logic...
```

---

## Audit Trail UI

### Admin Audit Log Viewer

**Features:**
- **Search & Filter:**
  - By user, event type, date range, resource
  - Full-text search on event details
- **Export:**
  - CSV/JSON export for compliance audits
  - Date range selection
- **Alerting:**
  - Real-time alerts for suspicious activity
  - Weekly summary reports

**UI Mockup:**
```
┌─────────────────────────────────────────────────────────┐
│ Audit Log                                                │
├─────────────────────────────────────────────────────────┤
│ Filters:                                                 │
│ User: [All Users ▼]  Event Type: [All ▼]                │
│ Date: [2026-02-01] to [2026-02-11]  [Search]            │
├─────────────────────────────────────────────────────────┤
│ Timestamp           User        Event Type     Resource  │
│ 2026-02-11 10:30    Alice       baseline.created bl_001 │
│ 2026-02-11 10:15    Bob         run.created      run_123│
│ 2026-02-11 09:45    Alice       data.exported    bl_001 │
│ 2026-02-11 09:30    Charlie     user.role_changed u_007 │
│ ...                                                       │
├─────────────────────────────────────────────────────────┤
│ [Export CSV] [Export JSON]                               │
└─────────────────────────────────────────────────────────┘
```

### API Endpoint

```python
@router.get("/api/v1/audit/events")
async def list_audit_events(
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = None,
    event_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    offset: int = 0,
    limit: int = 50
) -> List[AuditEvent]:
    """List audit events with filters"""

    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if start_date:
        query = query.where(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.where(AuditLog.timestamp <= end_date)

    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

@router.get("/api/v1/audit/events/export")
async def export_audit_events(
    format: str = "csv",  # csv or json
    ...  # same filters as above
):
    """Export audit events"""
    events = await list_audit_events(...)

    if format == "csv":
        return export_to_csv(events)
    else:
        return export_to_json(events)
```

---

## Compliance Frameworks

### SOC 2 Type II Readiness

**Control Objectives:**

| Control | Implementation | Evidence |
|---|---|---|
| **CC6.1:** Access controls | RLS policies, role-based permissions | Auth logs, RLS tests |
| **CC6.2:** Logging & monitoring | Audit log, metrics, alerts | Audit reports, dashboards |
| **CC6.3:** Data encryption | TLS, encrypted storage, encrypted backups | Config docs, SSL tests |
| **CC7.2:** Change management | Git, code review, CI/CD | Git history, PR approvals |
| **CC7.3:** Quality assurance | Automated tests, code coverage | Test reports, coverage >70% |
| **CC8.1:** Data backup | Daily backups, PITR, DR tested | Backup logs, DR drill reports |

**Audit Artifacts (Generated Quarterly):**
- User access matrix (who has access to what)
- Change log (all production deployments)
- Security incident log
- Backup/restore test results
- Penetration test reports (annual)

### GDPR Compliance

**Data Subject Rights:**

1. **Right to Access (Art. 15)**
```python
@router.get("/api/v1/gdpr/data-export")
async def export_user_data(user_id: str):
    """Export all data for a user"""
    return {
        "user_profile": await get_user(user_id),
        "baselines": await get_user_baselines(user_id),
        "drafts": await get_user_drafts(user_id),
        "runs": await get_user_runs(user_id),
        "audit_log": await get_user_audit_log(user_id)
    }
```

2. **Right to Erasure (Art. 17)**
```python
@router.delete("/api/v1/gdpr/delete-user")
async def delete_user_data(user_id: str, reason: str):
    """Delete all user data (irreversible)"""

    # Log the deletion request
    await create_audit_event(
        event_type="user.deleted",
        event_category="user_management",
        resource_type="user",
        resource_id=user_id,
        operation="delete",
        status="initiated",
        context={"reason": reason, "requested_by": current_user_id.get()}
    )

    # Anonymize audit logs (keep for legal, but anonymize)
    await db.execute(
        update(AuditLog)
        .where(AuditLog.user_id == user_id)
        .values(user_id="deleted_user", ip_address="0.0.0.0")
    )

    # Delete user data
    await delete_user_baselines(user_id)
    await delete_user_drafts(user_id)
    await delete_user_runs(user_id)
    await delete_user(user_id)

    # Confirm deletion
    await create_audit_event(
        event_type="user.deleted",
        event_category="user_management",
        resource_type="user",
        resource_id=user_id,
        operation="delete",
        status="completed"
    )
```

3. **Right to Data Portability (Art. 20)**
- Export in JSON format
- Include all baselines, runs, memos

4. **Right to Rectification (Art. 16)**
- Allow users to update their profile
- Audit trail of changes

5. **Right to Restrict Processing (Art. 18)**
- Allow users to pause LLM processing
- Maintain data but don't use for AI

**GDPR-Specific Tables:**
```sql
CREATE TABLE data_subject_requests (
  request_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  request_type TEXT NOT NULL,  -- access, erasure, portability, rectification
  status TEXT NOT NULL,         -- pending, in_progress, completed
  requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  notes TEXT
);

CREATE TABLE consent_records (
  consent_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  consent_type TEXT NOT NULL,  -- llm_processing, data_storage, analytics
  granted BOOLEAN NOT NULL,
  granted_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  ip_address TEXT,
  user_agent TEXT
);
```

### Financial Services Compliance

**Record Retention:**
- **Baselines, Runs, Memos:** 7 years (financial records)
- **Audit Logs:** 7 years
- **User Access Logs:** 2 years
- **LLM Call Logs:** 1 year (can be longer if needed)

**Audit Requirements:**
- Quarterly audit report generation
- Annual external audit support
- Real-time compliance dashboard

---

## Data Retention & Archival

### Retention Policy

```python
RETENTION_POLICY = {
    "audit_log": {
        "hot": 90,        # days in primary database
        "warm": 365,      # days in compressed database
        "cold": 2555,     # days in S3 (7 years)
        "delete_after": 2555
    },
    "baselines": {
        "active": None,   # Never auto-delete
        "archived": 2555  # 7 years
    },
    "runs": {
        "recent": 90,
        "archive": 365,
        "delete_after": 2555
    },
    "llm_call_logs": {
        "hot": 30,
        "archive": 365,
        "delete_after": 365
    }
}
```

### Archival Process

```python
# Scheduled job (daily)
@celery_app.task
async def archive_old_data():
    """Move old data to cold storage"""

    # Archive audit logs older than 90 days
    cutoff_date = datetime.utcnow() - timedelta(days=90)

    old_logs = await db.execute(
        select(AuditLog).where(AuditLog.timestamp < cutoff_date)
    )

    for log in old_logs.scalars():
        # Compress and move to S3
        await s3_client.put_object(
            Bucket='finmodel-archive',
            Key=f'audit_logs/{log.tenant_id}/{log.timestamp.year}/{log.audit_event_id}.json.gz',
            Body=gzip.compress(json.dumps(log.dict()).encode()),
            StorageClass='GLACIER'  # Cheapest storage tier
        )

        # Delete from hot database
        await db.execute(delete(AuditLog).where(AuditLog.audit_event_id == log.audit_event_id))

    # Similar for runs, drafts, etc.
```

---

## Security Incident Response

### Incident Types

1. **Unauthorized Access**
   - Failed login attempts (>5 in 5 min)
   - Permission denied (repeated)

2. **Data Breach**
   - Unauthorized data export
   - RLS bypass attempt
   - SQL injection attempt

3. **Anomalous Behavior**
   - Unusual LLM usage (spike)
   - Mass data deletion
   - API abuse (rate limit exceeded repeatedly)

### Incident Response Workflow

```
┌─────────────────────┐
│ 1. Detection        │  Automated alerts from monitoring
│    (Automated)      │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 2. Triage           │  Security team reviews alert
│    (Manual)         │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 3. Containment      │  Suspend user, revoke keys, block IP
│    (Automated/Man)  │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 4. Investigation    │  Review audit logs, trace actions
│    (Manual)         │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 5. Remediation      │  Fix vulnerability, restore data
│    (Manual)         │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 6. Notification     │  Notify affected users (if breach)
│    (Manual)         │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ 7. Post-Mortem      │  Document incident, improve processes
│    (Manual)         │
└─────────────────────┘
```

### Automated Containment

```python
# Alert rule triggers this
async def handle_security_incident(incident_type: str, user_id: str, details: dict):
    """Automated incident response"""

    if incident_type == "repeated_failed_login":
        # Temporarily lock account
        await lock_user_account(user_id, duration_minutes=30)

        # Notify user
        await send_email(
            to=get_user_email(user_id),
            subject="Suspicious login activity detected",
            body=f"Your account has been temporarily locked due to multiple failed login attempts. It will unlock automatically in 30 minutes."
        )

    elif incident_type == "rls_bypass_attempt":
        # Immediately suspend account
        await suspend_user_account(user_id)

        # Alert security team
        await send_alert_to_security_team(
            severity="CRITICAL",
            message=f"RLS bypass attempt detected for user {user_id}",
            details=details
        )

    # Log the incident
    await create_audit_event(
        event_type="security.incident",
        event_category="security",
        resource_type="user",
        resource_id=user_id,
        operation="incident_response",
        status="automated_containment",
        context={"incident_type": incident_type, "details": details}
    )
```

---

## Compliance Reporting

### Quarterly Compliance Report

Auto-generated report includes:

```python
@router.get("/api/v1/compliance/report")
async def generate_compliance_report(
    start_date: datetime,
    end_date: datetime
):
    """Generate compliance report for date range"""

    return {
        "period": {"start": start_date, "end": end_date},
        "user_access": {
            "total_users": await count_users(),
            "active_users": await count_active_users(start_date, end_date),
            "new_users": await count_new_users(start_date, end_date),
            "deleted_users": await count_deleted_users(start_date, end_date),
            "role_changes": await count_role_changes(start_date, end_date)
        },
        "data_activity": {
            "baselines_created": await count_baselines_created(start_date, end_date),
            "runs_executed": await count_runs_executed(start_date, end_date),
            "data_exports": await count_data_exports(start_date, end_date)
        },
        "security": {
            "failed_logins": await count_failed_logins(start_date, end_date),
            "permission_denials": await count_permission_denials(start_date, end_date),
            "security_incidents": await list_security_incidents(start_date, end_date)
        },
        "audit_log": {
            "total_events": await count_audit_events(start_date, end_date),
            "events_by_category": await count_events_by_category(start_date, end_date)
        },
        "gdpr_requests": {
            "access_requests": await count_gdpr_requests("access", start_date, end_date),
            "erasure_requests": await count_gdpr_requests("erasure", start_date, end_date),
            "portability_requests": await count_gdpr_requests("portability", start_date, end_date)
        }
    }
```

### SOC 2 Audit Package

Annual package for auditors:

```
soc2_audit_package_2026/
  ├── access_control_matrix.xlsx
  ├── change_log_2026.csv
  ├── backup_restore_tests.pdf
  ├── penetration_test_report.pdf
  ├── security_incidents_2026.csv
  ├── audit_logs_sample.csv
  ├── policy_documents/
  │   ├── security_policy.pdf
  │   ├── incident_response_plan.pdf
  │   ├── data_retention_policy.pdf
  │   └── business_continuity_plan.pdf
  └── test_evidence/
      ├── rls_test_results.pdf
      ├── encryption_verification.pdf
      └── ci_cd_pipeline_config.yaml
```

---

## Compliance Checklist

### Pre-Launch
- [ ] Audit logging implemented for all critical events
- [ ] Audit logs immutable and tamper-proof
- [ ] GDPR data export/deletion endpoints implemented
- [ ] Consent management system in place
- [ ] Data retention policy configured
- [ ] Encryption at rest and in transit
- [ ] Backup and DR procedures tested

### Ongoing (Quarterly)
- [ ] Generate compliance report
- [ ] Review audit logs for anomalies
- [ ] Test backup restore
- [ ] Update access control matrix
- [ ] Review and update policies

### Annual
- [ ] External security audit / penetration test
- [ ] SOC 2 audit (if applicable)
- [ ] Policy review and update
- [ ] Disaster recovery drill
- [ ] Compliance training for team
