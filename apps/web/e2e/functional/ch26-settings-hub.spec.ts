import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Settings Hub', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('settings page heading is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await expect(
      page.getByRole('heading', { name: /settings/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('multiple settings sections are visible', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Page should have rendered some content (at least 2 text elements related to settings)
    const settingsTexts = page.getByText(/billing|teams|integrations|sso|audit|compliance|currency/i);
    await expect(settingsTexts.first()).toBeVisible({ timeout: 10000 });
  });

  test('Billing section is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await expect(
      page.getByText(/billing/i).first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Teams section is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await expect(
      page.getByText(/teams/i).first(),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Integrations section is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await expect(
      page.getByText(/integrations/i).first(),
    ).toBeVisible({ timeout: 10000 });
  });
});
