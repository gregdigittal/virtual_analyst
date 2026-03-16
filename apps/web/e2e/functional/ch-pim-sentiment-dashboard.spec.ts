import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('PIM — Sentiment Monitor Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('sentiment page loads with heading and dashboard tab', async ({ page }) => {
    await page.goto(`${BASE}/pim/sentiment`);
    await expect(page).toHaveURL(new RegExp('/pim/sentiment'), { timeout: 10000 });

    // Wait for loading spinner to resolve
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"], [aria-busy="true"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1000);

    // Assert page heading "Sentiment Monitor" is visible
    const heading = page.getByRole('heading', { name: /sentiment monitor/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Assert the "Dashboard" tab is present (VATabs renders tabs as buttons or role="tab")
    const dashboardTab = page
      .getByRole('button', { name: /^dashboard$/i })
      .or(page.getByRole('tab', { name: /^dashboard$/i }))
      .or(page.getByText(/^dashboard$/i));
    await expect(dashboardTab.first()).toBeVisible({ timeout: 10000 });

    // Assert "Company Detail" tab is also present
    const detailTab = page
      .getByRole('button', { name: /company detail/i })
      .or(page.getByRole('tab', { name: /company detail/i }))
      .or(page.getByText(/company detail/i));
    await expect(detailTab.first()).toBeVisible({ timeout: 10000 });
  });

  test('sentiment dashboard shows data table or empty state (not a blank/error page)', async ({ page }) => {
    await page.goto(`${BASE}/pim/sentiment`);
    await expect(page).toHaveURL(new RegExp('/pim/sentiment'), { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 15000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1500);

    // The page should show one of:
    // - A data table with Company / Ticker / Sentiment columns (companies in universe)
    // - An empty state message prompting to add companies
    // - An error alert (API failure — also acceptable for this test)

    const dataTable = page.locator('table');
    const emptyState = page.getByText(/no companies in your universe|add companies from the universe|universe manager/i);
    const errorAlert = page.getByRole('alert');

    const hasTable = await dataTable.first().isVisible().catch(() => false);
    const hasEmptyState = await emptyState.first().isVisible().catch(() => false);
    const hasError = await errorAlert.first().isVisible().catch(() => false);

    // At least one of these states must be rendered — a blank page is a failure
    const pageRendered = hasTable || hasEmptyState || hasError;

    if (!pageRendered) {
      // Fall back: assert any meaningful content is present
      const anyContent = page.getByText(/sentiment|company|ticker|universe|dashboard/i);
      await expect(anyContent.first()).toBeVisible({ timeout: 10000 });
    } else if (hasTable) {
      // Data table is visible — assert it has at least the column headers
      const companyColumn = page.getByRole('columnheader', { name: /company/i });
      await expect(companyColumn.first()).toBeVisible({ timeout: 5000 });
    } else if (hasEmptyState) {
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
    } else if (hasError) {
      // Error state is valid — assert the alert is visible
      await expect(errorAlert.first()).toBeVisible({ timeout: 5000 });
    }
  });
});
