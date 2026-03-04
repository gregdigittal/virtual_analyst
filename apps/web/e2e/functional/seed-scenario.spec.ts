import { test, expect } from '@playwright/test';
import { TEST_USER, BASE_URL } from './fixtures/test-constants';
import * as fs from 'fs';
import * as path from 'path';

const BASE = BASE_URL || 'https://www.virtual-analyst.ai';

/**
 * seed-scenario.spec.ts
 *
 * Seeds the production test user account with baseline, draft, and run entities
 * so that downstream E2E tests (ch14, ch25, etc.) have data to work with.
 *
 * Strategy (hybrid — discovery-first):
 *   1. Login via UI → intercept Supabase auth response to capture access_token
 *   2. Navigate to a data page → intercept outgoing API request to discover
 *      the actual NEXT_PUBLIC_API_URL and working auth headers
 *   3. Use discovered URL + captured token for direct API calls via Playwright's
 *      `request` fixture (bypasses CORS) OR browser-context fetch as fallback
 *   4. Create baseline, run, and draft via POST endpoints
 *   5. Persist seeded IDs for downstream tests
 *
 * Run BEFORE other functional tests:
 *   npx playwright test e2e/functional/seed-scenario.spec.ts
 */

/** Path where seeded entity IDs are written for downstream tests */
const SEEDED_IDS_OUTPUT = path.resolve(__dirname, 'fixtures', 'seeded-ids.json');

/**
 * Minimal model_config_v1 payload that passes ModelConfig validation.
 */
function buildMinimalModelConfig(tenantId: string, baselineId: string) {
  return {
    artifact_type: 'model_config_v1',
    artifact_version: '1.0.0',
    tenant_id: tenantId,
    baseline_id: baselineId,
    baseline_version: 'v1',
    created_at: new Date().toISOString(),
    created_by: 'e2e-seed',
    metadata: {
      entity_name: 'E2E Seed Company',
      currency: 'USD',
      start_date: '2025-01-01',
      horizon_months: 12,
      resolution: 'monthly',
      fiscal_year_end_month: 12,
      tax_rate: 0.25,
      initial_cash: 100000,
      initial_equity: 500000,
    },
    assumptions: {
      revenue_streams: [
        {
          stream_id: 'rs_seed',
          label: 'Seed Revenue',
          stream_type: 'unit_sale',
          drivers: {
            volume: [
              {
                ref: 'drv:units',
                label: 'Units Sold',
                value_type: 'constant',
                value: 100,
                data_type: 'integer',
              },
            ],
            pricing: [
              {
                ref: 'drv:price',
                label: 'Unit Price',
                value_type: 'constant',
                value: 50,
                data_type: 'currency',
              },
            ],
            direct_costs: [],
          },
        },
      ],
      cost_structure: {
        variable_costs: [],
        fixed_costs: [
          {
            cost_id: 'fc_rent',
            label: 'Office Rent',
            category: 'sga',
            driver: {
              ref: 'drv:rent',
              label: 'Monthly Rent',
              value_type: 'constant',
              value: 5000,
              data_type: 'currency',
            },
          },
        ],
      },
      working_capital: {
        ar_days: { ref: 'drv:ar_days', label: 'AR Days', value_type: 'constant', value: 30, data_type: 'number' },
        ap_days: { ref: 'drv:ap_days', label: 'AP Days', value_type: 'constant', value: 45, data_type: 'number' },
        inv_days: { ref: 'drv:inv_days', label: 'Inv Days', value_type: 'constant', value: 15, data_type: 'number' },
      },
    },
    driver_blueprint: {
      nodes: [
        { node_id: 'n_units', type: 'driver', label: 'Units', ref: 'drv:units', classification: 'revenue' },
        { node_id: 'n_price', type: 'driver', label: 'Price', ref: 'drv:price', classification: 'revenue' },
        { node_id: 'n_revenue', type: 'output', label: 'Revenue', classification: 'revenue' },
      ],
      edges: [
        { from: 'n_units', to: 'n_revenue' },
        { from: 'n_price', to: 'n_revenue' },
      ],
      formulas: [
        {
          formula_id: 'f_revenue',
          output_node_id: 'n_revenue',
          expression: 'n_units * n_price',
          inputs: ['n_units', 'n_price'],
        },
      ],
    },
    integrity: {
      status: 'passed',
      checks: [],
    },
  };
}

test.describe('Seed Scenario — API-Driven Data Seeding', () => {
  test.setTimeout(300_000); // 5 minutes — backend cold start can take 2+ min

  test('Seed baseline, draft, and run for test user', async ({ page, request }) => {
    /* ──────────────────────────────────────────────────────────
     * Phase 1 — Login via UI and capture Supabase access token
     * ────────────────────────────────────────────────────────── */
    console.log('Phase 1: Logging in and capturing auth token…');

    // Set up response interception BEFORE navigating to login
    const authResponsePromise = page.waitForResponse(
      (res) => res.url().includes('/auth/v1/token') && res.status() === 200,
      { timeout: 30_000 },
    );

    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Capture the access token from the Supabase auth response
    let accessToken = '';
    let userId = '';
    let tenantId = '';

    try {
      const authResponse = await authResponsePromise;
      const authBody = await authResponse.json();
      accessToken = authBody.access_token || '';
      userId = authBody.user?.id || '';
      console.log(`  Captured token from Supabase auth response (user: ${userId})`);
    } catch (e) {
      console.log(`  Could not intercept Supabase auth response: ${e}`);
    }

    // Fallback: extract token from browser storage/cookies if intercept failed
    if (!accessToken) {
      console.log('  Trying fallback: extracting token from browser storage…');
      await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 });
      await page.waitForTimeout(2_000);

      accessToken = await page.evaluate(() => {
        for (const key of Object.keys(localStorage)) {
          if (key.includes('supabase') || key.includes('sb-')) {
            try {
              const data = JSON.parse(localStorage.getItem(key) || '');
              if (data?.access_token) return data.access_token as string;
              if (data?.currentSession?.access_token)
                return data.currentSession.access_token as string;
            } catch {}
          }
        }
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
          const [name, value] = cookie.trim().split('=');
          if (name?.includes('sb-') && name?.includes('-auth-token')) {
            try {
              const decoded = decodeURIComponent(value || '');
              const parsed = JSON.parse(decoded);
              if (parsed?.access_token) return parsed.access_token as string;
            } catch {}
          }
        }
        return '';
      });
    }

    // Wait for login redirect if we haven't already
    if (page.url().includes('/login')) {
      await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20_000 });
    }
    console.log(`  Login successful, token captured: ${!!accessToken}`);

    expect(accessToken, 'Failed to capture Supabase access token after login').toBeTruthy();

    // Decode JWT header to check signing algorithm
    if (accessToken) {
      try {
        const headerB64 = accessToken.split('.')[0];
        const header = JSON.parse(Buffer.from(headerB64, 'base64url').toString());
        console.log(`  JWT Header: ${JSON.stringify(header)}`);
      } catch (e) {
        console.log(`  Could not decode JWT header: ${e}`);
      }
    }

    // Extract tenant ID from the JWT payload
    if (!tenantId && accessToken) {
      try {
        const payload = JSON.parse(
          Buffer.from(accessToken.split('.')[1], 'base64').toString(),
        );
        userId = userId || payload.sub || '';
        tenantId =
          payload.app_metadata?.tenant_id ||
          payload.user_metadata?.tenant_id ||
          userId;
        console.log(`  Tenant ID from JWT: ${tenantId}`);
        console.log(`  JWT aud: ${payload.aud}, iss: ${payload.iss}, role: ${payload.role}`);
        console.log(`  JWT app_metadata: ${JSON.stringify(payload.app_metadata)}`);
      } catch (e) {
        console.log(`  Could not parse JWT: ${e}`);
      }
    }

    // Final fallback for tenant ID
    if (!tenantId) {
      tenantId = 'f004fe0c-da81-49ab-afab-9a9a8286211e';
      console.log(`  Using hardcoded tenant ID: ${tenantId}`);
    }

    /* ──────────────────────────────────────────────────────────
     * Phase 2 — Discover actual API URL by intercepting frontend requests
     *
     * The frontend's NEXT_PUBLIC_API_URL is baked into the JS bundle at build
     * time. Rather than guessing what it is, navigate to a data page and
     * intercept the outgoing API request to see the real URL + headers.
     * ────────────────────────────────────────────────────────── */
    console.log('Phase 2: Discovering API URL from frontend requests…');

    let discoveredApiBaseUrl = '';
    let discoveredAuthHeader = '';
    let discoveredTenantHeader = '';

    // Set up request interceptor to capture outgoing API calls
    const apiRequestPromise = new Promise<{
      url: string;
      authHeader: string;
      tenantHeader: string;
    }>((resolve) => {
      const timeout = setTimeout(() => {
        resolve({ url: '', authHeader: '', tenantHeader: '' });
      }, 30_000);

      page.on('request', (req) => {
        const url = req.url();
        // Look for any request that includes /api/v1/ (to the backend)
        if (url.includes('/api/v1/') && !url.includes('/auth/v1/') && req.method() === 'GET') {
          clearTimeout(timeout);
          resolve({
            url: url,
            authHeader: req.headers()['authorization'] || '',
            tenantHeader: req.headers()['x-tenant-id'] || '',
          });
        }
      });
    });

    // Navigate to baselines page — this triggers a GET /api/v1/baselines
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');

    const discovered = await apiRequestPromise;

    if (discovered.url) {
      // Extract the base URL (everything before /api/v1/)
      const apiV1Index = discovered.url.indexOf('/api/v1/');
      if (apiV1Index !== -1) {
        discoveredApiBaseUrl = discovered.url.substring(0, apiV1Index);
      }
      discoveredAuthHeader = discovered.authHeader;
      discoveredTenantHeader = discovered.tenantHeader;
      console.log(`  Discovered API base URL: ${discoveredApiBaseUrl}`);
      console.log(`  Discovered full request URL: ${discovered.url}`);
      console.log(`  Frontend has auth header: ${!!discoveredAuthHeader}`);
      console.log(`  Frontend tenant header: ${discoveredTenantHeader}`);

      // Also capture a fresh token from what the frontend is using
      if (discoveredAuthHeader && discoveredAuthHeader.startsWith('Bearer ')) {
        const frontendToken = discoveredAuthHeader.substring(7);
        if (frontendToken && frontendToken !== accessToken) {
          console.log('  Frontend is using a DIFFERENT token — switching to frontend token');
          accessToken = frontendToken;
          // Re-extract user/tenant from the new token
          try {
            const payload = JSON.parse(
              Buffer.from(accessToken.split('.')[1], 'base64').toString(),
            );
            userId = payload.sub || userId;
            tenantId =
              payload.app_metadata?.tenant_id ||
              payload.user_metadata?.tenant_id ||
              tenantId;
          } catch {}
        }
      }
    } else {
      console.log('  Could not discover API URL from frontend requests');
      console.log('  Falling back to Render backend URL');
      discoveredApiBaseUrl = 'https://virtual-analyst-api.onrender.com';
    }

    const API_BASE = discoveredApiBaseUrl || 'https://virtual-analyst-api.onrender.com';
    console.log(`  Using API base: ${API_BASE}`);

    /* ──────────────────────────────────────────────────────────
     * Phase 2.5 — Warm up the backend and check health
     * ────────────────────────────────────────────────────────── */
    console.log('Phase 2.5: Checking backend health…');

    let backendLive = false;
    for (let attempt = 1; attempt <= 6; attempt++) {
      try {
        const healthRes = await request.get(`${API_BASE}/api/v1/health/live`, {
          timeout: 60_000,
        });
        console.log(`  Liveness attempt ${attempt}: ${healthRes.status()}`);
        if (healthRes.ok()) { backendLive = true; break; }
      } catch (e) {
        console.log(`  Liveness attempt ${attempt} failed: ${e}`);
      }
      if (attempt < 6) await page.waitForTimeout(15_000);
    }

    if (!backendLive) {
      console.log('  FATAL: Backend completely unreachable — cannot seed data');
      test.skip(true, 'Backend unreachable');
      return;
    }

    // Check readiness (DB/Redis) but don't block on it
    for (let attempt = 1; attempt <= 4; attempt++) {
      try {
        const readyRes = await request.get(`${API_BASE}/api/v1/health/ready`, {
          timeout: 30_000,
        });
        const body = await readyRes.json().catch(() => ({}));
        console.log(`  Readiness attempt ${attempt}: ${readyRes.status()} ${JSON.stringify(body)}`);
        if (readyRes.ok()) break;
      } catch (e) {
        console.log(`  Readiness attempt ${attempt} failed: ${e}`);
      }
      if (attempt < 4) await page.waitForTimeout(10_000);
    }

    /* ──────────────────────────────────────────────────────────
     * Shared headers for direct API calls
     * ────────────────────────────────────────────────────────── */
    const apiHeaders = {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
      'X-User-ID': userId,
    };

    /* ──────────────────────────────────────────────────────────
     * Phase 3 — Check existing entities
     *
     * Try Playwright request fixture first. If it gets 401,
     * fall back to browser-context fetch (same auth as frontend).
     * ────────────────────────────────────────────────────────── */
    console.log('Phase 3: Checking existing entities…');

    let baselineId = '';
    let draftId = '';
    let runId = '';
    let usePlaywrightRequest = true;

    // Helper: make API call via Playwright's request fixture
    async function apiGet(path: string) {
      const res = await request.get(`${API_BASE}${path}`, {
        headers: apiHeaders,
        timeout: 30_000,
      });
      return { status: res.status(), body: await res.json().catch(() => ({})) };
    }

    // Helper: make API call via browser-context fetch (uses frontend's same-origin/CORS)
    async function browserApiGet(apiPath: string): Promise<{ status: number; body: unknown }> {
      return page.evaluate(
        async ({ baseUrl, path, token, tenant, user }) => {
          try {
            const res = await fetch(`${baseUrl}${path}`, {
              method: 'GET',
              headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'X-Tenant-ID': tenant,
                'X-User-ID': user,
              },
            });
            const body = await res.json().catch(() => ({}));
            return { status: res.status, body };
          } catch (e) {
            return { status: 0, body: { error: String(e) } };
          }
        },
        { baseUrl: API_BASE, path: apiPath, token: accessToken, tenant: tenantId, user: userId },
      );
    }

    // Helper: make API POST via browser-context fetch
    async function browserApiPost(
      apiPath: string,
      data: unknown,
    ): Promise<{ status: number; body: unknown }> {
      return page.evaluate(
        async ({ baseUrl, path, token, tenant, user, payload }) => {
          try {
            const res = await fetch(`${baseUrl}${path}`, {
              method: 'POST',
              headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                'X-Tenant-ID': tenant,
                'X-User-ID': user,
              },
              body: JSON.stringify(payload),
            });
            const body = await res.json().catch(() => ({}));
            return { status: res.status, body };
          } catch (e) {
            return { status: 0, body: { error: String(e) } };
          }
        },
        {
          baseUrl: API_BASE,
          path: apiPath,
          token: accessToken,
          tenant: tenantId,
          user: userId,
          payload: data,
        },
      );
    }

    // Test which method works: try Playwright request first, if 401 switch to browser fetch
    {
      const testResult = await apiGet('/api/v1/baselines');
      console.log(`  Playwright request GET /baselines → ${testResult.status}`);

      if (testResult.status === 401) {
        console.log('  Playwright request got 401 — trying browser-context fetch…');
        const browserResult = await browserApiGet('/api/v1/baselines');
        console.log(`  Browser fetch GET /baselines → ${browserResult.status}`);

        if (browserResult.status !== 401 && browserResult.status !== 0) {
          console.log('  ✓ Browser-context fetch works — switching to browser fetch mode');
          usePlaywrightRequest = false;
          const data = browserResult.body as Record<string, unknown>;
          const items = (data.items || data.baselines || []) as Array<Record<string, string>>;
          if (items.length > 0) {
            baselineId = items[0].baseline_id;
            console.log(`  Existing baseline: ${baselineId}`);
          }
        } else {
          // Both methods fail. Try getting a fresh token from the Supabase session in the browser
          console.log('  Both methods return 401. Trying fresh token from Supabase session…');
          const freshToken = await page.evaluate(async () => {
            // @supabase/ssr stores session — find it
            // Try method 1: cookies with chunked pattern sb-{ref}-auth-token.0, sb-{ref}-auth-token.1, ...
            const cookies = document.cookie.split(';').map((c) => c.trim());
            const tokenChunks: Record<string, string> = {};
            let tokenBase = '';
            for (const cookie of cookies) {
              const eqIdx = cookie.indexOf('=');
              if (eqIdx === -1) continue;
              const name = cookie.substring(0, eqIdx);
              const value = cookie.substring(eqIdx + 1);
              if (name.includes('sb-') && name.includes('-auth-token')) {
                // Chunked cookie: sb-{ref}-auth-token.0, sb-{ref}-auth-token.1, etc.
                const dotIdx = name.lastIndexOf('.');
                if (dotIdx !== -1) {
                  const base = name.substring(0, dotIdx);
                  const idx = name.substring(dotIdx + 1);
                  tokenBase = base;
                  tokenChunks[idx] = decodeURIComponent(value);
                } else {
                  // Non-chunked: the whole thing is in one cookie
                  try {
                    const parsed = JSON.parse(decodeURIComponent(value));
                    if (parsed?.access_token) return parsed.access_token as string;
                  } catch {}
                }
              }
            }
            // Reassemble chunked cookies
            if (tokenBase && Object.keys(tokenChunks).length > 0) {
              const sortedKeys = Object.keys(tokenChunks).sort(
                (a, b) => parseInt(a) - parseInt(b),
              );
              const assembled = sortedKeys.map((k) => tokenChunks[k]).join('');
              // assembled is base64-encoded JSON
              try {
                const decoded = atob(assembled);
                const parsed = JSON.parse(decoded);
                if (parsed?.access_token) return parsed.access_token as string;
              } catch {}
              // Maybe it's not base64; try parsing directly
              try {
                const parsed = JSON.parse(assembled);
                if (parsed?.access_token) return parsed.access_token as string;
              } catch {}
            }
            return '';
          });

          if (freshToken && freshToken !== accessToken) {
            console.log('  Found fresh token from cookies — retrying…');
            accessToken = freshToken;
            apiHeaders.Authorization = `Bearer ${freshToken}`;

            // Re-extract user/tenant
            try {
              const payload = JSON.parse(
                Buffer.from(freshToken.split('.')[1], 'base64').toString(),
              );
              userId = payload.sub || userId;
              tenantId =
                payload.app_metadata?.tenant_id ||
                payload.user_metadata?.tenant_id ||
                tenantId;
              apiHeaders['X-Tenant-ID'] = tenantId;
              apiHeaders['X-User-ID'] = userId;
            } catch {}

            const retryResult = await apiGet('/api/v1/baselines');
            console.log(`  Retry with fresh token → ${retryResult.status}`);
            if (retryResult.status !== 401) {
              const data = retryResult.body as Record<string, unknown>;
              const items = (data.items || data.baselines || []) as Array<Record<string, string>>;
              if (items.length > 0) {
                baselineId = items[0].baseline_id;
                console.log(`  Existing baseline: ${baselineId}`);
              }
            }
          }
        }
      } else if (testResult.status === 200) {
        const data = testResult.body as Record<string, unknown>;
        const items = (data.items || data.baselines || []) as Array<Record<string, string>>;
        if (items.length > 0) {
          baselineId = items[0].baseline_id;
          console.log(`  Existing baseline: ${baselineId}`);
        }
      } else {
        console.log(`  Unexpected status: ${testResult.status} ${JSON.stringify(testResult.body)}`);
      }
    }

    // Check drafts
    try {
      const res = usePlaywrightRequest
        ? await apiGet('/api/v1/drafts')
        : await browserApiGet('/api/v1/drafts');
      console.log(`  GET /drafts → ${res.status}`);
      if (res.status === 200) {
        const data = res.body as Record<string, unknown>;
        const items = (data.items || data.drafts || []) as Array<Record<string, string>>;
        if (items.length > 0) {
          draftId = items[0].draft_session_id;
          console.log(`  Existing draft: ${draftId}`);
        }
      }
    } catch (e) {
      console.log(`  Drafts check error: ${e}`);
    }

    // Check runs
    try {
      const res = usePlaywrightRequest
        ? await apiGet('/api/v1/runs')
        : await browserApiGet('/api/v1/runs');
      console.log(`  GET /runs → ${res.status}`);
      if (res.status === 200) {
        const data = res.body as Record<string, unknown>;
        const items = (data.items || data.runs || []) as Array<Record<string, string>>;
        if (items.length > 0) {
          runId = items[0].run_id;
          console.log(`  Existing run: ${runId}`);
        }
      }
    } catch (e) {
      console.log(`  Runs check error: ${e}`);
    }

    console.log(
      `  Existing: baseline=${baselineId || 'none'}, draft=${draftId || 'none'}, run=${runId || 'none'}`,
    );

    /* ──────────────────────────────────────────────────────────
     * Phase 4 — Create Baseline (if needed)
     * ────────────────────────────────────────────────────────── */
    if (!baselineId) {
      console.log('Phase 4: Creating baseline…');

      // First try marketplace templates
      let createdViaMarketplace = false;
      try {
        const templatesRes = usePlaywrightRequest
          ? await apiGet('/api/v1/marketplace/templates')
          : await browserApiGet('/api/v1/marketplace/templates');
        console.log(`  GET /marketplace/templates → ${templatesRes.status}`);

        if (templatesRes.status === 200) {
          const templates = templatesRes.body as Record<string, unknown>;
          const items = (templates.items || templates.templates || []) as Array<
            Record<string, string>
          >;
          if (items.length > 0) {
            const templateId = items[0].template_id || items[0].id;
            console.log(`  Using marketplace template: ${templateId}`);

            const useRes = usePlaywrightRequest
              ? await (async () => {
                  const r = await request.post(
                    `${API_BASE}/api/v1/marketplace/templates/${templateId}/use`,
                    {
                      headers: apiHeaders,
                      data: {
                        label: 'E2E Seed Company',
                        fiscal_year: '2025',
                        answers: {},
                      },
                      timeout: 30_000,
                    },
                  );
                  return {
                    status: r.status(),
                    body: await r.json().catch(() => ({})),
                  };
                })()
              : await browserApiPost(
                  `/api/v1/marketplace/templates/${templateId}/use`,
                  {
                    label: 'E2E Seed Company',
                    fiscal_year: '2025',
                    answers: {},
                  },
                );
            console.log(`  POST template use → ${useRes.status}`);

            if (useRes.status >= 200 && useRes.status < 300) {
              const result = useRes.body as Record<string, string>;
              baselineId = result.baseline_id || '';
              createdViaMarketplace = !!baselineId;
              console.log(`  Created baseline from template: ${baselineId}`);
            } else {
              console.log(`  Template use failed: ${JSON.stringify(useRes.body).substring(0, 200)}`);
            }
          }
        }
      } catch (e) {
        console.log(`  Marketplace approach failed: ${e}`);
      }

      // Fallback: create baseline directly
      if (!createdViaMarketplace) {
        console.log('  Marketplace unavailable — creating baseline with minimal config…');

        const tempId = `bl_seed${Date.now().toString(36)}`;
        const modelConfig = buildMinimalModelConfig(tenantId, tempId);

        const createRes = usePlaywrightRequest
          ? await (async () => {
              const r = await request.post(`${API_BASE}/api/v1/baselines`, {
                headers: apiHeaders,
                data: { model_config: modelConfig },
                timeout: 30_000,
              });
              return {
                status: r.status(),
                body: await r.json().catch(() => ({})),
              };
            })()
          : await browserApiPost('/api/v1/baselines', { model_config: modelConfig });
        console.log(`  POST /baselines → ${createRes.status}`);

        if (createRes.status >= 200 && createRes.status < 300) {
          const result = createRes.body as Record<string, string>;
          baselineId = result.baseline_id || '';
          console.log(`  Created baseline: ${baselineId}`);
        } else {
          console.log(
            `  Baseline creation failed: ${JSON.stringify(createRes.body).substring(0, 300)}`,
          );
          if (createRes.status >= 500 || createRes.status === 0) {
            console.log('  WARNING: Backend issue — skipping seeding');
            test.skip(true, 'Backend issue — cannot create baseline');
            return;
          }
        }
      }
    } else {
      console.log('Phase 4: Baseline already exists, skipping');
    }

    expect(baselineId, 'No baseline ID after seeding attempt').toBeTruthy();

    /* ──────────────────────────────────────────────────────────
     * Phase 5 — Create Run from Baseline (if needed)
     * ────────────────────────────────────────────────────────── */
    if (!runId && baselineId) {
      console.log('Phase 5: Creating run…');

      const createRunRes = usePlaywrightRequest
        ? await (async () => {
            const r = await request.post(`${API_BASE}/api/v1/runs`, {
              headers: apiHeaders,
              data: { baseline_id: baselineId, mode: 'deterministic' },
              timeout: 60_000,
            });
            return {
              status: r.status(),
              body: await r.json().catch(() => ({})),
            };
          })()
        : await browserApiPost('/api/v1/runs', {
            baseline_id: baselineId,
            mode: 'deterministic',
          });
      console.log(`  POST /runs → ${createRunRes.status}`);

      if (createRunRes.status >= 200 && createRunRes.status < 300) {
        const result = createRunRes.body as Record<string, string>;
        runId = result.run_id || '';
        console.log(`  Created run: ${runId}`);
      } else {
        console.log(
          `  Run creation failed: ${JSON.stringify(createRunRes.body).substring(0, 300)}`,
        );
        console.log('  WARNING: Proceeding without run');
      }
    } else if (runId) {
      console.log('Phase 5: Run already exists, skipping');
    }

    /* ──────────────────────────────────────────────────────────
     * Phase 6 — Create Draft (if needed)
     * ────────────────────────────────────────────────────────── */
    if (!draftId) {
      console.log('Phase 6: Creating draft…');

      const createDraftRes = usePlaywrightRequest
        ? await (async () => {
            const r = await request.post(`${API_BASE}/api/v1/drafts`, {
              headers: apiHeaders,
              data: baselineId
                ? { parent_baseline_id: baselineId, parent_baseline_version: 'v1' }
                : {},
              timeout: 30_000,
            });
            return {
              status: r.status(),
              body: await r.json().catch(() => ({})),
            };
          })()
        : await browserApiPost(
            '/api/v1/drafts',
            baselineId
              ? { parent_baseline_id: baselineId, parent_baseline_version: 'v1' }
              : {},
          );
      console.log(`  POST /drafts → ${createDraftRes.status}`);

      if (createDraftRes.status >= 200 && createDraftRes.status < 300) {
        const result = createDraftRes.body as Record<string, string>;
        draftId = result.draft_session_id || '';
        console.log(`  Created draft: ${draftId}`);
      } else {
        console.log(
          `  Draft creation failed: ${JSON.stringify(createDraftRes.body).substring(0, 300)}`,
        );
      }
    } else {
      console.log('Phase 6: Draft already exists, skipping');
    }

    /* ──────────────────────────────────────────────────────────
     * Phase 7 — Persist seeded IDs to JSON file
     * ────────────────────────────────────────────────────────── */
    console.log('Phase 7: Writing seeded IDs…');

    const seededIds = {
      tenantId,
      baselineId,
      draftId,
      runId,
      apiUrl: `${API_BASE}/api/v1`,
      seededAt: new Date().toISOString(),
    };

    fs.mkdirSync(path.dirname(SEEDED_IDS_OUTPUT), { recursive: true });
    fs.writeFileSync(SEEDED_IDS_OUTPUT, JSON.stringify(seededIds, null, 2));
    console.log(`  Wrote → ${SEEDED_IDS_OUTPUT}`);
    console.log(`  ${JSON.stringify(seededIds, null, 2)}`);

    /* ──────────────────────────────────────────────────────────
     * Phase 8 — Verify entities are visible in the UI
     * ────────────────────────────────────────────────────────── */
    if (baselineId) {
      console.log('Phase 8: Verifying entities in UI…');

      await page.goto(`${BASE}/baselines`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(5_000);

      const baselineLink = page.locator('a[href*="/baselines/"]').first();
      const hasBaseline = await baselineLink
        .isVisible({ timeout: 15_000 })
        .catch(() => false);
      console.log(`  Baselines visible: ${hasBaseline}`);
      expect(
        hasBaseline,
        'Baseline should be visible on /baselines after seeding',
      ).toBeTruthy();
    }

    /* ──────────────────────────────────────────────────────────
     * Summary
     * ────────────────────────────────────────────────────────── */
    console.log('\n=== Seed Scenario Complete ===');
    console.log(`  API URL:     ${seededIds.apiUrl}`);
    console.log(`  Tenant ID:   ${tenantId}`);
    console.log(`  Baseline ID: ${baselineId}`);
    console.log(`  Draft ID:    ${draftId || 'N/A'}`);
    console.log(`  Run ID:      ${runId || 'N/A'}`);
    console.log('==============================\n');
  });
});
