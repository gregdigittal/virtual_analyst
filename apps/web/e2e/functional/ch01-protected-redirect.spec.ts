import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch01 — Protected Route Redirect', () => {
  test('unauthenticated access to /dashboard redirects to /login', async ({ page }) => {
    // Ensure no session cookies are present
    await page.context().clearCookies();

    await page.goto(`${BASE}/dashboard`);

    // Should be redirected to the login page (possibly with a ?next= param)
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test('unauthenticated access to /baselines redirects to /login', async ({ page }) => {
    await page.context().clearCookies();

    await page.goto(`${BASE}/baselines`);

    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test('unauthenticated access to /runs redirects to /login', async ({ page }) => {
    await page.context().clearCookies();

    await page.goto(`${BASE}/runs`);

    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test('after login, user is sent to /dashboard', async ({ page }) => {
    await page.context().clearCookies();

    // Navigate to protected page first
    await page.goto(`${BASE}/dashboard`);
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });

    // Log in
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Should land on /dashboard (or the originally requested page)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });
});
