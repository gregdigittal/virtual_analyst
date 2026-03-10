import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch02 — Sidebar Navigation', () => {
  test('sidebar shows expected navigation links and Baselines navigates to /baselines', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /dashboard
    await page.goto(`${BASE}/dashboard`);
    await expect(page).toHaveURL(`${BASE}/dashboard`, { timeout: 10000 });

    // Assert required sidebar links are visible
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Marketplace' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Baselines' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible({ timeout: 10000 });

    // Click 'Baselines' and assert navigation to /baselines
    await page.getByRole('link', { name: 'Baselines' }).click();
    await expect(page).toHaveURL(`${BASE}/baselines`, { timeout: 10000 });
  });
});
