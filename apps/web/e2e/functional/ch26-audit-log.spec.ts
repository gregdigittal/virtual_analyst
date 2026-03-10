import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Audit Log', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('audit log link is visible on settings page', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Settings page has a card with "Audit Log" title linking to /settings/audit
    await expect(page.getByText('Audit Log')).toBeVisible({ timeout: 10000 });
  });

  test('clicking audit log navigates to audit page', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.getByText('Audit Log').click();
    await page.waitForURL(/\/settings\/audit/, { timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible({ timeout: 10000 });
  });

  test('audit log page heading is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Audit Log' })).toBeVisible({ timeout: 15000 });
  });

  test('audit log table or empty state is visible after loading', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Wait for loading spinner to disappear
    await expect(page.getByText('Loading audit events')).toBeHidden({ timeout: 20000 });
    // Either a table or an empty state message should be shown
    const tableOrEmpty = page.locator('table')
      .or(page.getByText('No events match the selected filters.'));
    await expect(tableOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('filter controls are visible — User ID and Event type', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // User ID text input and Event type select should be present
    await expect(page.getByText('User ID')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Event type')).toBeVisible({ timeout: 10000 });
  });

  test('filter controls include date range — Start date and End date', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByText('Start date')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('End date')).toBeVisible({ timeout: 10000 });
  });

  test('audit log table has Time column header (timestamp)', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByText('Loading audit events')).toBeHidden({ timeout: 20000 });
    // If a table is shown, it should have Time column header
    const hasTable = await page.locator('table').isVisible();
    if (hasTable) {
      await expect(page.getByRole('columnheader', { name: 'Time' })).toBeVisible({ timeout: 5000 });
    } else {
      // Empty state — structure is correct, just no data
      await expect(page.getByText('No events match the selected filters.')).toBeVisible();
    }
  });

  test('audit log table has User column header', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByText('Loading audit events')).toBeHidden({ timeout: 20000 });
    const hasTable = await page.locator('table').isVisible();
    if (hasTable) {
      await expect(page.getByRole('columnheader', { name: 'User' })).toBeVisible({ timeout: 5000 });
    } else {
      await expect(page.getByText('No events match the selected filters.')).toBeVisible();
    }
  });

  test('audit log table has Type column header (action type)', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByText('Loading audit events')).toBeHidden({ timeout: 20000 });
    const hasTable = await page.locator('table').isVisible();
    if (hasTable) {
      await expect(page.getByRole('columnheader', { name: 'Type' })).toBeVisible({ timeout: 5000 });
    } else {
      await expect(page.getByText('No events match the selected filters.')).toBeVisible();
    }
  });

  test('Export CSV and Refresh buttons are visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/audit`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(page.getByRole('button', { name: /export csv/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /refresh/i })).toBeVisible({ timeout: 10000 });
  });
});
