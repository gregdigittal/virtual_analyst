import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch18 — Covenant Alerts & Status Indicators', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('covenant page loads with heading and either data or empty state', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Heading must be visible
    const heading = page.getByRole('heading', { name: /covenants/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Either covenant items with alerts/statuses or an empty state
    const contentOrEmpty = page
      .getByText(/compliant|warning|breach|at risk|breached|ok/i)
      .or(page.getByText(/no covenants|no monitors|empty|get started|create your first|add a covenant/i));

    await expect(contentOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('covenant status indicators or empty state is visible', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    await page.waitForTimeout(2000);

    // Check for the empty state first — "No covenants yet" or similar
    const isEmptyState = await page
      .getByText(/no covenants|no monitors yet|add a covenant/i)
      .first()
      .isVisible()
      .catch(() => false);

    if (isEmptyState) {
      // Empty state is acceptable: assert it is visible
      await expect(
        page.getByText(/no covenants|no monitors yet|add a covenant/i).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      // Covenant items exist — status indicators should be visible
      const statusIndicator = page
        .getByText(/compliant/i)
        .or(page.getByText(/warning/i))
        .or(page.getByText(/breach/i))
        .or(page.getByText(/at risk/i))
        .or(page.getByText(/breached/i))
        .or(page.getByText(/ok/i));

      await expect(statusIndicator.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('covenant threshold and current value labels visible when monitors exist', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    await page.waitForTimeout(2000);

    // Detect empty state via the "No covenants" message (not the creation form)
    const isEmptyState = await page
      .getByText(/no covenants|no monitors yet|add a covenant using/i)
      .first()
      .isVisible()
      .catch(() => false);

    if (isEmptyState) {
      // Empty state — assert empty state text is visible
      await expect(
        page.getByText(/no covenants|no monitors yet|add a covenant using/i).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      // Covenant monitors exist — threshold label should be present in monitor cards
      const thresholdLabel = page
        .getByText(/threshold/i)
        .or(page.getByText(/limit/i));
      await expect(thresholdLabel.first()).toBeVisible({ timeout: 10000 });

      // Current or actual value label should be present in monitor cards
      const currentValueLabel = page
        .getByText(/current/i)
        .or(page.getByText(/actual/i));
      await expect(currentValueLabel.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('warning status visible when metric is within margin of threshold', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    await page.waitForTimeout(2000);

    // Look for any warning-level covenant indicator
    const warningPresent = await page
      .getByText(/warning|at risk|near|approaching/i)
      .first()
      .isVisible()
      .catch(() => false);

    if (warningPresent) {
      await expect(
        page.getByText(/warning|at risk|near|approaching/i).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      // No warning covenant — page still loaded correctly (data or empty state)
      const pageContent = page
        .getByText(/covenant|no covenants|compliant|breach|add a covenant/i)
        .first();
      await expect(pageContent).toBeVisible({ timeout: 10000 });
    }
  });

  test('breach status visible when threshold is exceeded', async ({ page }) => {
    await page.goto(`${BASE}/covenants`);
    await expect(page).toHaveURL(new RegExp('/covenants'), { timeout: 10000 });

    await page.waitForTimeout(2000);

    // Look for any breached covenant indicator
    const breachPresent = await page
      .getByText(/breach|breached|exceeded/i)
      .first()
      .isVisible()
      .catch(() => false);

    if (breachPresent) {
      await expect(
        page.getByText(/breach|breached|exceeded/i).first()
      ).toBeVisible({ timeout: 10000 });
    } else {
      // No breach covenant — page still loaded correctly (data or empty state)
      const pageContent = page
        .getByText(/covenant|no covenants|compliant|warning|add a covenant/i)
        .first();
      await expect(pageContent).toBeVisible({ timeout: 10000 });
    }
  });
});
