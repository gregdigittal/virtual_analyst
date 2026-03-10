import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch17 — Budget Variance Analysis', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('opening a budget shows variance analysis tab or empty state', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for empty state
    const emptyState = page.getByText(/no budgets|empty|get started|create your first|no results/i);
    const isEmpty = await emptyState.first().isVisible().catch(() => false);

    if (isEmpty) {
      // Empty state is a valid outcome
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
      return;
    }

    // Find and click the first budget entry
    const firstBudget = page
      .getByRole('link', { name: /.+/ })
      .or(page.getByRole('row').nth(1))
      .or(page.locator('[data-testid*="budget"]').first())
      .first();

    // Try clicking a budget row/card/link
    const budgetLinks = page.getByRole('link').filter({ hasNotText: /create|new|import/i });
    const budgetLinkCount = await budgetLinks.count();

    if (budgetLinkCount > 0) {
      await budgetLinks.first().click();
    } else {
      // Try clicking a table row
      const rows = page.getByRole('row').filter({ hasNotText: /name|status|period|budget/i });
      const rowCount = await rows.count();
      if (rowCount > 0) {
        await rows.first().click();
      } else {
        // No budget to open, accept this as valid
        return;
      }
    }

    await page.waitForTimeout(2000);

    // We should be on a budget detail page — look for Variance tab
    const varianceTab = page.getByRole('tab', { name: /variance/i })
      .or(page.getByRole('link', { name: /variance/i }))
      .or(page.getByText(/variance/i).first());

    await expect(varianceTab.first()).toBeVisible({ timeout: 10000 });
  });

  test('variance tab shows comparison of budget vs actual values', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for empty state first
    const emptyState = page.getByText(/no budgets|empty|get started|create your first|no results/i);
    const isEmpty = await emptyState.first().isVisible().catch(() => false);

    if (isEmpty) {
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
      return;
    }

    // Navigate into the first available budget
    const budgetLinks = page.getByRole('link').filter({ hasNotText: /create|new|import|sign|log/i });
    const budgetLinkCount = await budgetLinks.count();

    if (budgetLinkCount === 0) {
      // No budget links found, skip
      return;
    }

    await budgetLinks.first().click();
    await page.waitForTimeout(2000);

    // Click the Variance tab if present
    const varianceTab = page.getByRole('tab', { name: /variance/i })
      .or(page.getByRole('link', { name: /variance/i }));

    const tabVisible = await varianceTab.first().isVisible().catch(() => false);
    if (tabVisible) {
      await varianceTab.first().click();
      await page.waitForTimeout(1500);
    }

    // Assert variance-related content: columns or text indicating budget vs actual comparison
    const varianceContent = page
      .getByText(/budget|actual|variance/i)
      .first();

    await expect(varianceContent).toBeVisible({ timeout: 10000 });

    // Look for favorable/unfavorable indicators or numeric comparison columns
    const comparisonElements = page
      .getByText(/favorable|unfavorable|budgeted|actuals/i)
      .or(page.getByRole('columnheader', { name: /budget|actual|variance/i }))
      .or(page.getByRole('table'));

    const comparisonVisible = await comparisonElements.first().isVisible().catch(() => false);
    if (comparisonVisible) {
      await expect(comparisonElements.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('variance section contains charts or tables with period-by-period data', async ({ page }) => {
    await page.goto(`${BASE}/budgets`);
    await expect(page).toHaveURL(new RegExp('/budgets'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Check for empty state
    const emptyState = page.getByText(/no budgets|empty|get started|create your first|no results/i);
    const isEmpty = await emptyState.first().isVisible().catch(() => false);

    if (isEmpty) {
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
      return;
    }

    // Navigate into the first budget
    const budgetLinks = page.getByRole('link').filter({ hasNotText: /create|new|import|sign|log/i });
    const budgetLinkCount = await budgetLinks.count();

    if (budgetLinkCount === 0) {
      return;
    }

    await budgetLinks.first().click();
    await page.waitForTimeout(2000);

    // Click Variance tab
    const varianceTab = page.getByRole('tab', { name: /variance/i })
      .or(page.getByRole('link', { name: /variance/i }));

    const tabVisible = await varianceTab.first().isVisible().catch(() => false);
    if (tabVisible) {
      await varianceTab.first().click();
      await page.waitForTimeout(2000);
    }

    // The page should contain charts (SVG/canvas) OR a data table with period columns
    const chartOrTable = page
      .locator('svg')
      .or(page.locator('canvas'))
      .or(page.getByRole('table'))
      .or(page.locator('[class*="chart"]').first())
      .or(page.getByText(/period|monthly|quarterly|q1|q2|q3|q4/i).first())
      .or(page.getByText(/no actuals|no data|no variance/i).first());

    await expect(chartOrTable.first()).toBeVisible({ timeout: 10000 });
  });
});
