import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Currency Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('currency section is accessible from settings', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Click the Currency nav link/tab if present
    const currencyLink = page.getByRole('link', { name: /currency/i });
    if (await currencyLink.isVisible()) {
      await currencyLink.click();
    } else {
      const currencyTab = page.getByRole('tab', { name: /currency/i });
      if (await currencyTab.isVisible()) {
        await currencyTab.click();
      } else {
        // Navigate directly
        await page.goto(`${BASE}/settings/currency`);
      }
    }
    await expect(page.getByText(/currency/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('base currency display or selector is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/currency`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Base currency label or selector
    const baseCurrency = page
      .getByText(/base currency/i)
      .or(page.getByLabel(/base currency/i))
      .or(page.getByRole('combobox', { name: /base currency/i }));
    await expect(baseCurrency.first()).toBeVisible({ timeout: 15000 });
  });

  test('currency list or FX rate table is shown', async ({ page }) => {
    await page.goto(`${BASE}/settings/currency`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Currency list, FX rate table, or supported currencies section
    const rateContent = page
      .getByText(/exchange rate|fx rate|supported currencies|currencies/i)
      .or(page.getByRole('table'))
      .or(page.getByRole('list').filter({ hasText: /usd|eur|gbp|zar/i }));
    await expect(rateContent.first()).toBeVisible({ timeout: 15000 });
  });

  test('add currency or update rates control exists', async ({ page }) => {
    await page.goto(`${BASE}/settings/currency`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Control to add currencies or update rates
    const control = page
      .getByRole('button', { name: /add currency/i })
      .or(page.getByRole('button', { name: /update rates?/i }))
      .or(page.getByRole('button', { name: /refresh rates?/i }))
      .or(page.getByRole('link', { name: /add currency/i }))
      .or(page.getByText(/add currency|update rates?/i));
    await expect(control.first()).toBeVisible({ timeout: 15000 });
  });

  test('FX rate feed or manual update option is present', async ({ page }) => {
    await page.goto(`${BASE}/settings/currency`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Automatic feed or manual entry for exchange rates
    const feedOption = page.getByText(/automatic|manual|feed|rate source|update/i);
    await expect(feedOption.first()).toBeVisible({ timeout: 15000 });
  });
});
