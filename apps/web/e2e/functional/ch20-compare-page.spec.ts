import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch20 — Compare Page', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('compare page heading contains Compare or Comparison', async ({ page }) => {
    await page.goto(`${BASE}/compare`);
    await page.waitForTimeout(2000);

    const heading = page
      .getByRole('heading', { name: /compare|comparison/i })
      .or(page.getByText(/compare|comparison/i).first());

    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('entity or run selection controls are visible', async ({ page }) => {
    await page.goto(`${BASE}/compare`);
    await page.waitForTimeout(2000);

    // Dropdowns, select boxes, or buttons for choosing entities/runs to compare
    const selectionControl = page
      .getByRole('combobox')
      .or(page.locator('select').first())
      .or(page.getByRole('button', { name: /add|select|choose|entity|run/i }).first())
      .or(page.getByText(/select entity|select run|choose entity|choose run|add entity|add run/i).first())
      .or(page.locator('input[type="search"]').first())
      .or(page.getByPlaceholder(/search|select|entity|run/i).first());

    await expect(selectionControl.first()).toBeVisible({ timeout: 10000 });
  });

  test('comparison table or chart area exists', async ({ page }) => {
    await page.goto(`${BASE}/compare`);
    await page.waitForTimeout(2000);

    // Table, chart canvas, or the entity/run selection panel that is the comparison interface
    const comparisonArea = page
      .getByRole('table')
      .or(page.locator('canvas').first())
      .or(page.getByRole('heading', { name: /select entities|select runs|compare entities|compare runs/i }).first())
      .or(page.getByText(/select entities|select runs|no entities found|no runs found|compare.*entities|compare.*runs/i).first())
      .or(page.getByRole('button', { name: /compare \d+ entities|compare \d+ runs/i }).first());

    await expect(comparisonArea.first()).toBeVisible({ timeout: 10000 });
  });
});
