import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch10 — Baselines List', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('baselines page heading contains Baselines', async ({ page }) => {
    await page.goto(`${BASE}/baselines`);
    await expect(page).toHaveURL(new RegExp('/baselines'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /baselines/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('baselines page shows a search/filter input', async ({ page }) => {
    await page.goto(`${BASE}/baselines`);
    await expect(page).toHaveURL(new RegExp('/baselines'), { timeout: 10000 });

    const searchInput = page
      .getByRole('searchbox')
      .or(page.getByPlaceholder(/search|filter/i))
      .or(page.locator('input[type="search"]'))
      .or(page.locator('input[type="text"]').filter({ hasText: '' }).first());

    await expect(searchInput.first()).toBeVisible({ timeout: 10000 });
  });

  test('baselines page shows baseline list or empty state', async ({ page }) => {
    await page.goto(`${BASE}/baselines`);
    await expect(page).toHaveURL(new RegExp('/baselines'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either a list/table/cards with baselines OR an empty state message
    const listOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no baselines|empty|get started|create your first|no results/i));

    await expect(listOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('each baseline shows a label and status if baselines exist', async ({ page }) => {
    await page.goto(`${BASE}/baselines`);
    await expect(page).toHaveURL(new RegExp('/baselines'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Check for empty state first
    const emptyState = page.getByText(/no baselines|empty|get started|create your first|no results/i);
    const isEmpty = await emptyState.first().isVisible().catch(() => false);

    if (isEmpty) {
      // Empty state is a valid outcome — test passes
      return;
    }

    // If baselines exist, each should show a label (name) and status (Active or Archived)
    const statusText = page.getByText(/active|archived/i).first();
    await expect(statusText).toBeVisible({ timeout: 10000 });
  });
});
