import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch11 — Drafts List', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('drafts page heading contains Drafts', async ({ page }) => {
    await page.goto(`${BASE}/drafts`);
    await expect(page).toHaveURL(new RegExp('/drafts'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /drafts/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('drafts page shows draft cards/rows or empty state', async ({ page }) => {
    await page.goto(`${BASE}/drafts`);
    await expect(page).toHaveURL(new RegExp('/drafts'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either a list/table/cards with drafts OR an empty state message
    const listOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no drafts|empty|get started|create your first|no results/i));

    await expect(listOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });
});
