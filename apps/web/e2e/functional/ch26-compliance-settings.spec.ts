import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Compliance Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('compliance & GDPR heading is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/compliance`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByRole('heading', { name: /compliance.*gdpr/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('data export button is visible in compliance settings', async ({ page }) => {
    await page.goto(`${BASE}/settings/compliance`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByRole('button', { name: /export data/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('data deletion or anonymization button is visible in compliance settings', async ({ page }) => {
    await page.goto(`${BASE}/settings/compliance`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // The app implements data deletion as anonymization
    await expect(
      page.getByRole('button', { name: /anonymize|delet/i }),
    ).toBeVisible({ timeout: 10000 });
  });
});
