import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Integrations', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('integrations page heading is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/integrations`);
    await expect(
      page.getByRole('heading', { name: /integrations/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Xero and QuickBooks providers are shown', async ({ page }) => {
    await page.goto(`${BASE}/settings/integrations`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // The page always shows Connect buttons for Xero and QuickBooks
    await expect(
      page.getByRole('button', { name: /connect xero/i }),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole('button', { name: /connect quickbooks/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Connect buttons are available for unconnected integrations', async ({ page }) => {
    await page.goto(`${BASE}/settings/integrations`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    const connectXero = page.getByRole('button', { name: /connect xero/i });
    const connectQB = page.getByRole('button', { name: /connect quickbooks/i });
    await expect(connectXero).toBeVisible({ timeout: 10000 });
    await expect(connectQB).toBeVisible({ timeout: 10000 });
    await expect(connectXero).toBeEnabled();
    await expect(connectQB).toBeEnabled();
  });

  test('integration connection status or empty state is shown', async ({ page }) => {
    await page.goto(`${BASE}/settings/integrations`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });

    // Wait for spinner to go away (loading state)
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading integrations…"]'),
      { timeout: 10000 },
    ).catch(() => {});

    // Either connection cards with status, or the empty-state message
    const hasConnections = await page
      .getByText(/status:/i)
      .isVisible()
      .catch(() => false);

    if (hasConnections) {
      // If there are connected integrations, each card shows "Status:"
      await expect(page.getByText(/status:/i).first()).toBeVisible({ timeout: 5000 });
    } else {
      // No connections seeded — the empty state must be visible
      await expect(
        page.getByText(/no connections yet/i),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('page description mentions Xero and QuickBooks', async ({ page }) => {
    await page.goto(`${BASE}/settings/integrations`);
    await expect(
      page.getByText(/xero or quickbooks/i),
    ).toBeVisible({ timeout: 10000 });
  });
});
