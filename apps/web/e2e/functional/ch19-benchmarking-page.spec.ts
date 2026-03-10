import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch19 — Benchmarking Page', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('benchmarking page heading contains Benchmark or Peer', async ({ page }) => {
    await page.goto(`${BASE}/benchmark`);
    await page.waitForTimeout(2000);

    const heading = page
      .getByRole('heading', { name: /benchmark|peer/i })
      .or(page.getByText(/benchmarking|peer comparison|industry comparison/i).first());

    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('industry comparison controls or charts are visible', async ({ page }) => {
    await page.goto(`${BASE}/benchmark`);
    await page.waitForTimeout(2000);

    // Industry selector dropdowns, chart, table, comparison text, or peer/KPI description
    const comparisonElement = page
      .getByRole('combobox')
      .or(page.locator('select').first())
      .or(page.locator('canvas').first())
      .or(page.getByRole('table'))
      .or(page.getByText(/compare your kpis|peer aggregate|peer benchmark|industry|sector|percentile|revenue growth|margin|efficiency/i).first());

    await expect(comparisonElement.first()).toBeVisible({ timeout: 10000 });
  });

  test('opt-in toggle or data sharing notice exists', async ({ page }) => {
    await page.goto(`${BASE}/benchmark`);
    await page.waitForTimeout(2000);

    // Opt-in toggle, checkbox, or data sharing notice
    const optInElement = page
      .getByRole('checkbox', { name: /opt.?in|share|contribute|participate/i })
      .or(page.getByRole('switch', { name: /opt.?in|share|contribute|participate/i }))
      .or(page.getByText(/opt.?in|data sharing|share your data|contribute data|anonymized|privacy/i).first())
      .or(page.locator('label').filter({ hasText: /opt.?in|share data|contribute/i }).first());

    await expect(optInElement.first()).toBeVisible({ timeout: 10000 });
  });
});
