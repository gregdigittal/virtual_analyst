import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch13 — Changeset Dry Run / Preview', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('dry run or empty state is visible on changesets page', async ({ page }) => {
    await page.goto(`${BASE}/changesets`);
    await expect(page).toHaveURL(new RegExp('/changesets'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    // Check if any changesets are present
    const dryRunButton = page
      .getByRole('button', { name: /dry run/i })
      .or(page.getByRole('button', { name: /preview/i }))
      .or(page.getByText(/dry run/i))
      .or(page.getByText(/preview impact/i));

    const emptyState = page.getByText(
      /no changesets|no changes|empty|get started|create your first|no results|haven't created/i
    );

    // Either a dry run/preview control exists, or the empty state guides the user
    const hasDryRun = await dryRunButton.first().isVisible().catch(() => false);
    const hasEmptyState = await emptyState.first().isVisible().catch(() => false);

    expect(hasDryRun || hasEmptyState).toBe(true);
  });

  test('if a changeset exists, dry run or preview button is actionable', async ({ page }) => {
    await page.goto(`${BASE}/changesets`);
    await expect(page).toHaveURL(new RegExp('/changesets'), { timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(2000);

    const dryRunButton = page
      .getByRole('button', { name: /dry run/i })
      .or(page.getByRole('button', { name: /preview/i }));

    const isVisible = await dryRunButton.first().isVisible().catch(() => false);

    if (isVisible) {
      // Button should be enabled and clickable
      await expect(dryRunButton.first()).toBeEnabled({ timeout: 5000 });
    } else {
      // No changesets — empty state should guide the user
      const emptyState = page.getByText(
        /no changesets|no changes|empty|get started|create your first|no results|haven't created/i
      );
      await expect(emptyState.first()).toBeVisible({ timeout: 5000 });
    }
  });
});
