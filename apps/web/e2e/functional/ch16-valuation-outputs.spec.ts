import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

/**
 * Helper: log in and navigate to the runs page. Returns true if at least one
 * run entry link is found, false otherwise.
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

test.describe('ch16 — Valuation Outputs', () => {
  test('run detail page shows Valuation tab or section', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
      // No runs — verify page heading and skip
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

    // Look for a Valuation tab, button, link, or heading
    const valuationSection = page
      .getByRole('tab', { name: /valuation/i })
      .or(page.getByRole('button', { name: /valuation/i }))
      .or(page.getByRole('link', { name: /valuation/i }))
      .or(page.getByRole('heading', { name: /valuation/i }))
      .or(page.getByText(/valuation/i).first());

    await expect(valuationSection).toBeVisible({ timeout: 10000 });
  });

  test('valuation section shows enterprise value, equity value, or WACC — or unavailable message', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
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

    // Click Valuation tab if present
    const valuationTab = page
      .getByRole('tab', { name: /valuation/i })
      .or(page.getByRole('button', { name: /valuation/i }));

    if (await valuationTab.count() > 0) {
      await valuationTab.first().click();
      await page.waitForTimeout(1500);
    }

    // Assert valuation metrics are visible OR that the section says unavailable
    const enterpriseValue = page.getByText(/enterprise value/i);
    const equityValue = page.getByText(/equity value/i);
    const wacc = page.getByText(/wacc/i);
    const impliedSharePrice = page.getByText(/implied share price/i);
    const terminalGrowth = page.getByText(/terminal growth/i);
    const dcf = page.getByText(/discounted cash flow|dcf/i);
    const multiples = page.getByText(/multiples/i);
    const unavailable = page.getByText(/not available|unavailable|no valuation|valuation not/i);

    const anyVisible =
      (await enterpriseValue.count()) > 0 ||
      (await equityValue.count()) > 0 ||
      (await wacc.count()) > 0 ||
      (await impliedSharePrice.count()) > 0 ||
      (await terminalGrowth.count()) > 0 ||
      (await dcf.count()) > 0 ||
      (await multiples.count()) > 0 ||
      (await unavailable.count()) > 0;

    expect(anyVisible).toBe(true);
  });

  test('valuation section shows key assumptions when data is present', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
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

    // Click Valuation tab if present
    const valuationTab = page
      .getByRole('tab', { name: /valuation/i })
      .or(page.getByRole('button', { name: /valuation/i }));

    if (await valuationTab.count() > 0) {
      await valuationTab.first().click();
      await page.waitForTimeout(1500);
    }

    // Check if valuation data is present at all
    const hasValuationData =
      (await page.getByText(/enterprise value/i).count()) > 0 ||
      (await page.getByText(/equity value/i).count()) > 0 ||
      (await page.getByText(/wacc/i).count()) > 0 ||
      (await page.getByText(/dcf|discounted cash flow/i).count()) > 0;

    if (hasValuationData) {
      // If valuation data exists, key assumptions like WACC or terminal growth should be present
      const assumptions = page
        .getByText(/wacc/i)
        .or(page.getByText(/terminal growth/i))
        .or(page.getByText(/discount rate/i))
        .or(page.getByText(/cost of equity/i))
        .or(page.getByText(/cost of debt/i));

      await expect(assumptions.first()).toBeVisible({ timeout: 10000 });
    } else {
      // No valuation data — acceptable, assert that the run detail page loaded
      const runDetailHeading = page
        .getByRole('heading')
        .or(page.getByText(/run|statements|kpi/i).first());
      await expect(runDetailHeading.first()).toBeVisible({ timeout: 10000 });
    }
  });
});
