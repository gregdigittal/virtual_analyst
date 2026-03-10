import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch18 — Covenants Page', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('covenants page heading contains Covenants', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /covenants/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Covenant or Add Monitor button is visible', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    const createBtn = page.getByRole('button', { name: /create covenant|add monitor|add covenant|new covenant/i })
      .or(page.getByRole('link', { name: /create covenant|add monitor|add covenant|new covenant/i }));

    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('covenants page shows covenant monitors or empty state', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either covenant cards/table or an empty state message
    const listOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no covenants|empty|get started|create your first|no monitors|no results/i));

    await expect(listOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });
});
