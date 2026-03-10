import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch12 — Scenarios Page', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('scenarios page heading contains Scenarios', async ({ page }) => {
    await page.goto(`${BASE}/scenarios`);
    await expect(page).toHaveURL(new RegExp('/scenarios'), { timeout: 10000 });

    const heading = page.getByRole('heading', { name: /scenarios/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('scenarios page shows a button to create a new scenario', async ({ page }) => {
    await page.goto(`${BASE}/scenarios`);
    await expect(page).toHaveURL(new RegExp('/scenarios'), { timeout: 10000 });

    // Button may be labeled "Create Scenario", "New scenario", or similar
    const createButton = page.getByRole('button', { name: /create scenario|new scenario/i })
      .or(page.getByRole('link', { name: /create scenario|new scenario/i }))
      .or(page.getByText(/create scenario/i).first());
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
  });

  test('scenarios page shows scenario cards or empty state', async ({ page }) => {
    await page.goto(`${BASE}/scenarios`);
    await expect(page).toHaveURL(new RegExp('/scenarios'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Either scenario cards/list OR an empty state message
    const cardsOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('table'))
      .or(page.getByRole('grid'))
      .or(page.getByText(/no scenarios|empty|get started|create your first|no results/i))
      .or(page.getByText(/best case|base case|worst case/i));

    await expect(cardsOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });
});
