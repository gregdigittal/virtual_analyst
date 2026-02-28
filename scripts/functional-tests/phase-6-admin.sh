#!/usr/bin/env bash
# phase-6-admin.sh — Ch26: Settings and Administration
# Manual ref: docs/user-manual/26-settings-and-admin.md
set -euo pipefail
source "$(dirname "$0")/lib/test-helpers.sh"

log_phase "Phase 6: Admin (Ch26)"

# ── Ch26: Settings and Administration ──────────────────────────

run_tdd_test "ch26-settings-hub" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Settings page is a card-based hub with sections for Billing,
Integrations, Teams, SSO/SAML, Audit Log, Compliance, and Currency
Management. Each card links to its configuration sub-page.

TASK:
1. Log in and navigate to /settings
2. Assert the page heading contains 'Settings'
3. Assert multiple settings cards or sections are visible
4. Assert at least these sections exist: Billing, Teams, Integrations
5. Save to apps/web/e2e/functional/ch26-settings-hub.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-teams-management" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Teams section lets tenant administrators manage team members.
Admins can invite new users, assign roles, and remove members.
The team list shows each member's name, email, role, and status.

TASK:
1. Log in and navigate to /settings (then click Teams)
2. Assert a team member list is visible
3. Assert an 'Invite' or 'Add Member' button exists
4. Assert each member shows a name and role
5. Save to apps/web/e2e/functional/ch26-teams-management.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-billing-page" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Billing section shows the current plan tier, usage meters
(LLM tokens, Monte Carlo runs, sync events), and payment method.
Users can upgrade or downgrade their plan.

TASK:
1. Log in and navigate to /settings (then click Billing)
2. Assert the current plan tier is displayed
3. Assert usage meter(s) are visible
4. Assert plan upgrade/downgrade options exist
5. Save to apps/web/e2e/functional/ch26-billing-page.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-integrations" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Integrations section shows available third-party connections:
Xero and QuickBooks (via OAuth 2.0). Each integration card shows
its connection status and a Connect/Disconnect button.

TASK:
1. Log in and navigate to /settings (then click Integrations)
2. Assert integration cards are visible (Xero, QuickBooks)
3. Assert each shows a connection status
4. Assert Connect buttons are available for unconnected integrations
5. Save to apps/web/e2e/functional/ch26-integrations.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-audit-log" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Audit Log provides an immutable record of all significant
actions. Entries show timestamp, user, action type, and affected
entity. The log is searchable and filterable by date range and
action type.

TASK:
1. Log in and navigate to /settings (then click Audit Log)
2. Assert audit log entries or a table is visible
3. Assert search/filter controls exist
4. Assert entries show timestamp, user, and action
5. Save to apps/web/e2e/functional/ch26-audit-log.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-currency-management" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Currency section lets users configure multi-currency support
and FX rates. Users can set a base currency, add supported
currencies, and update exchange rates manually or via automatic
feeds.

TASK:
1. Log in and navigate to /settings (then click Currency)
2. Assert base currency display or selection is visible
3. Assert currency list or FX rate table is shown
4. Assert an 'Add Currency' or 'Update Rates' control exists
5. Save to apps/web/e2e/functional/ch26-currency-management.spec.ts
6. Run and report RED or GREEN"

run_tdd_test "ch26-compliance-settings" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The Compliance section provides GDPR tools including data export
requests, data deletion requests, and consent management. It shows
compliance status and available actions.

TASK:
1. Log in and navigate to /settings (then click Compliance)
2. Assert compliance or GDPR controls are visible
3. Assert data export and deletion request options exist
4. Save to apps/web/e2e/functional/ch26-compliance-settings.spec.ts
5. Run and report RED or GREEN"

run_tdd_test "ch26-sso-config" \
"SPECIFICATION (from docs/user-manual/26-settings-and-admin.md):
The SSO/SAML section allows enterprise administrators to configure
single sign-on with their identity provider. Fields include IdP
metadata URL, entity ID, and certificate. SSO can be enabled or
disabled per tenant.

TASK:
1. Log in and navigate to /settings (then click SSO or SAML)
2. Assert SSO configuration fields are visible
3. Assert an enable/disable toggle exists
4. Assert IdP configuration fields (URL, entity ID) are shown
5. Save to apps/web/e2e/functional/ch26-sso-config.spec.ts
6. Run and report RED or GREEN"

log_phase_complete "Phase 6"
