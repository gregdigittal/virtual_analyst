import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch05 — Excel Connections Page Loads', () => {
  test('connections page shows heading, create button, and list or empty state after login', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /excel-connections
    await page.goto(`${BASE}/excel-connections`);

    // Assert page heading contains 'Connection' or 'Excel'
    await expect(
      page.locator('h1, h2').filter({ hasText: /connection|excel/i }).first()
    ).toBeVisible({ timeout: 15000 });

    // Assert a 'Create Connection' or 'New Connection' button is visible
    await expect(
      page.getByRole('button', { name: /create connection|new connection/i })
    ).toBeVisible({ timeout: 10000 });

    // Wait for the loading spinner to resolve (if present)
    await page.waitForSelector('text=/loading connections/i', { state: 'hidden', timeout: 15000 }).catch(() => {});

    // Assert either a list of connections OR an empty state message is present
    const connectionRow = page.locator('table tr, [role="row"], [role="listitem"]').first();
    const emptyState = page.getByText(/no connections|no excel connections|get started|create your first|you have no/i).first();
    // Also accept a generic content section that rendered any connections data
    const connectionCard = page.locator('[data-testid*="connection"], .connection-item').first();

    const hasConnectionRow = await connectionRow.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasConnectionCard = await connectionCard.isVisible().catch(() => false);

    expect(hasConnectionRow || hasEmptyState || hasConnectionCard).toBe(true);
  });
});
