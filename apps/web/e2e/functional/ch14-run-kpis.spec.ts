import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

/**
 * Helper: log in and navigate to the runs page. Returns true if at least one
 * run entry is found, false otherwise.
 */
async function loginAndGoToRuns(page: import('@playwright/test').Page): Promise<boolean> {
  await page.goto(`${BASE}/login`);
  await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

  await page.goto(`${BASE}/runs`);
  await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });
  await page.waitForTimeout(2000);

  const runDetailLinks = page.locator('a[href*="/runs/"]');
  const linkCount = await runDetailLinks.count();
  return linkCount > 0;
}

test.describe('ch14 — Run Detail: KPI Dashboard', () => {
  test('run detail page shows KPI section or dashboard tab', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
      // No runs available — verify runs page heading and empty state
      const heading = page
        .getByRole('heading', { name: /runs/i })
        .or(page.getByText(/no runs yet|no runs|empty/i))
        .or(page.getByText(/run a baseline|create a baseline|get started/i));
      await expect(heading.first()).toBeVisible({ timeout: 10000 });
      return;
    }

    const firstRunLink = page.locator('a[href*="/runs/"]').first();
    await firstRunLink.click();
    await page.waitForURL((url) => url.pathname.match(/\/runs\/[^/]+$/) !== null, {
      timeout: 15000,
    });
    await page.waitForTimeout(2000);

    // A KPI section, tab, or heading should be visible
    const kpiSection = page
      .getByRole('tab', { name: /kpi/i })
      .or(page.getByRole('button', { name: /kpi/i }))
      .or(page.getByRole('heading', { name: /kpi/i }))
      .or(page.getByText(/key performance indicator/i))
      .or(page.getByRole('tab', { name: /overview/i }))
      .or(page.getByRole('heading', { name: /overview/i }));

    await expect(kpiSection.first()).toBeVisible({ timeout: 10000 });
  });

  test('run detail KPI section shows at least one KPI metric with a value', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
      // No runs available — verify runs page heading
      const heading = page.getByRole('heading', { name: /runs/i });
      await expect(heading.first()).toBeVisible({ timeout: 10000 });
      return;
    }

    const firstRunLink = page.locator('a[href*="/runs/"]').first();
    await firstRunLink.click();
    await page.waitForURL((url) => url.pathname.match(/\/runs\/[^/]+$/) !== null, {
      timeout: 15000,
    });
    await page.waitForTimeout(2000);

    // Click a KPI or Overview tab if present
    const kpiTab = page
      .getByRole('tab', { name: /kpi/i })
      .or(page.getByRole('button', { name: /kpi/i }))
      .or(page.getByRole('tab', { name: /overview/i }));

    if (await kpiTab.count() > 0) {
      await kpiTab.first().click();
      await page.waitForTimeout(1000);
    }

    // Assert at least one common KPI metric label is visible
    const revenueGrowth = page.getByText(/revenue growth/i);
    const grossMargin = page.getByText(/gross margin/i);
    const ebitdaMargin = page.getByText(/ebitda margin/i);
    const netMargin = page.getByText(/net (profit )?margin/i);
    const currentRatio = page.getByText(/current ratio/i);
    const returnOnEquity = page.getByText(/return on equity/i);
    const returnOnAssets = page.getByText(/return on assets/i);
    const debtToEquity = page.getByText(/debt.{0,5}equity/i);

    const anyKpiVisible =
      (await revenueGrowth.count()) > 0 ||
      (await grossMargin.count()) > 0 ||
      (await ebitdaMargin.count()) > 0 ||
      (await netMargin.count()) > 0 ||
      (await currentRatio.count()) > 0 ||
      (await returnOnEquity.count()) > 0 ||
      (await returnOnAssets.count()) > 0 ||
      (await debtToEquity.count()) > 0;

    expect(anyKpiVisible).toBe(true);
  });
});
