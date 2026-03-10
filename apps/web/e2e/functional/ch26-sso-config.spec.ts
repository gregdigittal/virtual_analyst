import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — SSO / SAML Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('SSO / SAML page heading is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByRole('heading', { name: /sso.*saml/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test('SSO configuration status is displayed', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Page shows "Status: Configured" or "Status: Not configured"
    await expect(
      page.getByText(/status:/i),
    ).toBeVisible({ timeout: 10000 });
  });

  test('enable / disable SSO toggle exists', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Spec requires an enable/disable toggle (checkbox or switch role)
    const toggle =
      page.getByRole('switch', { name: /enable|disable|sso/i }).or(
        page.locator('input[type="checkbox"][name*="enabl"]'),
      ).or(
        page.getByRole('checkbox', { name: /enable|sso/i }),
      );
    await expect(toggle.first()).toBeVisible({ timeout: 10000 });
  });

  test('IdP metadata URL field is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByText(/idp metadata url/i),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Entity ID field is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByText(/entity id/i),
    ).toBeVisible({ timeout: 10000 });
  });

  test('IdP certificate field is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByText(/idp certificate/i),
    ).toBeVisible({ timeout: 10000 });
  });

  test('Save configuration button is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/sso`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await expect(
      page.getByRole('button', { name: /save configuration/i }),
    ).toBeVisible({ timeout: 10000 });
  });
});
