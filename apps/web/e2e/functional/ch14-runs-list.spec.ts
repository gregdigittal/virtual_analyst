import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch14 — Runs List', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('runs page heading contains Runs', async ({ page }) => {
    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /runs/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('runs page shows run entries or empty state', async ({ page }) => {
    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either a list/table/cards with runs OR an empty state message
    const listOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no runs|empty|get started|create your first|no results/i));

    await expect(listOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('run entries show a status when runs exist', async ({ page }) => {
    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Check if there are any run entries (rows, list items, or cards)
    const runEntries = page
      .getByRole('row')
      .or(page.getByRole('listitem'))
      .or(page.locator('[data-testid*="run"]'));

    const count = await runEntries.count();

    if (count > 1) {
      // Runs exist — assert that status labels are visible (success, error, or run mode)
      const statusText = page.getByText(/success|error|deterministic|monte carlo/i);
      await expect(statusText.first()).toBeVisible({ timeout: 10000 });
    } else {
      // No runs — empty state is acceptable
      const emptyState = page.getByText(/no runs|empty|get started|create your first|no results/i);
      const heading = page.getByRole('heading', { name: /runs/i });
      const visible = (await emptyState.count()) > 0 || (await heading.count()) > 0;
      expect(visible).toBe(true);
    }
  });
});
