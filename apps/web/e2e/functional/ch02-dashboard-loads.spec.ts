import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch02 — Dashboard Loads', () => {
  test('dashboard page shows summary cards and navigation after login', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /dashboard
    await page.goto(`${BASE}/dashboard`);

    // Assert the page URL is /dashboard
    await expect(page).toHaveURL(`${BASE}/dashboard`, { timeout: 10000 });

    // Assert the page heading is visible
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible({ timeout: 10000 });

    // Assert at least one summary card label is visible
    // The dashboard always renders "Recent runs", "Pending tasks", "Unread notifications" cards
    await expect(page.getByText('Recent runs').first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Pending tasks').first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Unread notifications').first()).toBeVisible({ timeout: 10000 });

    // Assert sidebar navigation is visible — sidebar has nav group labels and links
    // VASidebar renders group labels like "SETUP", "CONFIGURE", "ANALYZE" and link labels like "Baselines"
    await expect(page.getByRole('link', { name: 'Baselines' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: 'Runs' })).toBeVisible({ timeout: 10000 });
  });
});
