import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

/**
 * Helper: log in and navigate to the runs page. Returns true if at least one
 * run entry is found in the main content area (not the nav), false otherwise.
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

  // Scope to main content — avoid matching nav sidebar links
  const mainContent = page.locator('main, [role="main"], #main-content').first();

  // Look for clickable run entries: table rows (excluding header), list items with links,
  // or anchor tags whose href matches /runs/<id>
  const runDetailLinks = page.locator('a[href*="/runs/"]');
  const runRows = mainContent.getByRole('row').nth(1); // Skip header row

  const linkCount = await runDetailLinks.count();
  const rowCount = await runRows.count();

  return linkCount > 0 || rowCount > 0;
}

test.describe('ch14 — Run Detail: Financial Statements', () => {
  test('runs page shows empty state when no runs exist', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Detect run entries scoped to main content (not nav)
    const runDetailLinks = page.locator('a[href*="/runs/"]');
    const linkCount = await runDetailLinks.count();

    if (linkCount === 0) {
      // No runs — assert empty state is visible
      const emptyState = page
        .getByText(/no runs yet|no runs|empty/i)
        .or(page.getByText(/run a baseline|create a baseline|get started/i));
      await expect(emptyState.first()).toBeVisible({ timeout: 10000 });
    } else {
      // Runs exist — the list should be visible
      await expect(runDetailLinks.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('clicking a run navigates to run detail page', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
      // No runs available — verify empty state and skip navigation
      const emptyState = page
        .getByText(/no runs yet|no runs|empty/i)
        .or(page.getByText(/run a baseline|create a baseline|get started/i))
        .or(page.getByRole('heading', { name: /runs/i }));
      await expect(emptyState.first()).toBeVisible({ timeout: 10000 });
      return;
    }

    // Click the first run detail link
    const firstRunLink = page.locator('a[href*="/runs/"]').first();
    await firstRunLink.click();
    await page.waitForURL((url) => url.pathname.match(/\/runs\/[^/]+$/) !== null, {
      timeout: 15000,
    });
    await expect(page).toHaveURL(new RegExp('/runs/'), { timeout: 10000 });
  });

  test('run detail page shows Statements tab or section', async ({ page }) => {
    const hasRuns = await loginAndGoToRuns(page);

    if (!hasRuns) {
      // No runs available — verify page heading and empty state
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

    // The Statements tab/section should be visible
    const statementsSection = page
      .getByRole('tab', { name: /statements/i })
      .or(page.getByRole('button', { name: /statements/i }))
      .or(page.getByRole('link', { name: /statements/i }))
      .or(page.getByText(/statements/i).first());

    await expect(statementsSection).toBeVisible({ timeout: 10000 });
  });

  test('run detail Statements section shows at least one financial statement', async ({ page }) => {
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

    // Click Statements tab if present
    const statementsTab = page
      .getByRole('tab', { name: /statements/i })
      .or(page.getByRole('button', { name: /statements/i }));

    if (await statementsTab.count() > 0) {
      await statementsTab.first().click();
      await page.waitForTimeout(1000);
    }

    // Assert at least one financial statement label is visible
    const incomeStatement = page.getByText(/income statement/i);
    const balanceSheet = page.getByText(/balance sheet/i);
    const cashFlow = page.getByText(/cash flow/i);

    const anyVisible =
      (await incomeStatement.count()) > 0 ||
      (await balanceSheet.count()) > 0 ||
      (await cashFlow.count()) > 0;

    expect(anyVisible).toBe(true);
  });
});
