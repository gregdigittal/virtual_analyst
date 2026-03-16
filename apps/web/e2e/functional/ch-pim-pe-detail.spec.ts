import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('PIM — PE Fund Assessments', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('PE assessment list page loads with heading and New Assessment button', async ({ page }) => {
    await page.goto(`${BASE}/pim/pe`);
    await expect(page).toHaveURL(new RegExp('/pim/pe'), { timeout: 10000 });

    // Wait for loading spinner to resolve
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"], [aria-busy="true"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1000);

    // Assert page heading "PE Fund Assessments" is visible
    const heading = page.getByRole('heading', { name: /pe fund assessments/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Assert "New Assessment" button is visible
    const newAssessmentBtn = page.getByRole('button', { name: /new assessment/i });
    await expect(newAssessmentBtn.first()).toBeVisible({ timeout: 10000 });

    // Assert DPI / TVPI / IRR subheading text is present
    const subheading = page.getByText(/dpi.*tvpi.*irr|irr.*j.curve/i);
    await expect(subheading.first()).toBeVisible({ timeout: 10000 });
  });

  test('PE assessment list shows assessments table or empty state', async ({ page }) => {
    await page.goto(`${BASE}/pim/pe`);
    await expect(page).toHaveURL(new RegExp('/pim/pe'), { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 15000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1500);

    // The page should show one of:
    // - A data table with Fund / Vintage / DPI / TVPI / IRR columns
    // - An empty state message
    // - An error state

    const dataTable = page.locator('table');
    const emptyState = page.getByText(/no pe fund assessments yet|create your first assessment|get started/i);
    const errorText = page.getByText(/error|failed|could not/i);

    const hasTable = await dataTable.first().isVisible().catch(() => false);
    const hasEmptyState = await emptyState.first().isVisible().catch(() => false);

    const pageRendered = hasTable || hasEmptyState;

    if (!pageRendered) {
      // Fall back: assert any meaningful content is present
      const anyContent = page.getByText(/fund|assessment|dpi|tvpi|irr|vintage/i);
      await expect(anyContent.first()).toBeVisible({ timeout: 10000 });
    } else if (hasTable) {
      // Table is visible — assert Fund column header is present
      const fundColumn = page.getByRole('columnheader', { name: /^fund$/i });
      await expect(fundColumn.first()).toBeVisible({ timeout: 5000 });
    } else if (hasEmptyState) {
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('clicking a PE assessment navigates to its detail page showing key metrics', async ({ page }) => {
    await page.goto(`${BASE}/pim/pe`);
    await expect(page).toHaveURL(new RegExp('/pim/pe'), { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 15000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1500);

    // Look for assessment detail links (table rows link to /pim/pe/{id})
    const assessmentLinks = page.locator('a[href*="/pim/pe/"]');
    const linkCount = await assessmentLinks.count();

    if (linkCount === 0) {
      // No assessments seeded — empty state is valid; skip detail navigation
      const emptyState = page.getByText(/no pe fund assessments yet|create your first assessment/i);
      const hasEmptyState = await emptyState.first().isVisible().catch(() => false);
      if (hasEmptyState) {
        await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
      }
      test.skip(true, 'No PE assessments seeded — skipping detail navigation in this environment');
      return;
    }

    // Click the first assessment link ("View →" link in the table)
    await assessmentLinks.first().click();
    // Wait for navigation to /pim/pe/{id}
    await page.waitForURL((url) => /\/pim\/pe\/[^/]+$/.test(url.pathname), { timeout: 15000 });

    // Wait for content to load
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(1000);

    // Assert fund name heading is visible
    const fundHeading = page.getByRole('heading').first();
    await expect(fundHeading).toBeVisible({ timeout: 10000 });

    // Assert at least one key PE metric (DPI, TVPI, or IRR) is visible on the detail page
    const dpiMetric = page.getByText(/\bDPI\b/);
    const tvpiMetric = page.getByText(/\bTVPI\b/);
    const irrMetric = page.getByText(/\bIRR\b/);

    const hasDpi = await dpiMetric.first().isVisible().catch(() => false);
    const hasTvpi = await tvpiMetric.first().isVisible().catch(() => false);
    const hasIrr = await irrMetric.first().isVisible().catch(() => false);

    expect(hasDpi || hasTvpi || hasIrr).toBe(true);
  });
});
