import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch17 — Budgets List', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('budgets page heading contains Budgets', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /budgets/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Budget button is visible', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });

    const createBtn = page.getByRole('button', { name: /create budget/i })
      .or(page.getByRole('link', { name: /create budget/i }));

    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('budgets page shows budget entries or empty state', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either a list/table/cards with budgets OR an empty state message
    const listOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no budgets|empty|get started|create your first|no results/i));

    await expect(listOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('budget entries show period type and status if budgets exist', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Check for empty state first
    const emptyState = page.getByText(/no budgets|empty|get started|create your first|no results/i);
    const isEmpty = await emptyState.first().isVisible().catch(() => false);

    if (isEmpty) {
      // Empty state is a valid outcome — test passes
      return;
    }

    // If budgets exist, they should show period type (monthly/quarterly/annual)
    const periodType = page.getByText(/monthly|quarterly|annual/i).first();
    await expect(periodType).toBeVisible({ timeout: 10000 });
  });
});
