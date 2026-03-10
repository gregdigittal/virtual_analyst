import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch02 — Dashboard Recent Activity', () => {
  test('dashboard shows recent activity section with items or empty state', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /dashboard
    await page.goto(`${BASE}/dashboard`);
    await expect(page).toHaveURL(`${BASE}/dashboard`, { timeout: 10000 });

    // Wait for dashboard content to fully load
    await page.waitForLoadState('networkidle', { timeout: 15000 });

    // Assert the dashboard heading is visible (confirms we are on the right page)
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible({ timeout: 10000 });

    // --- Recent Activity Section ---
    // The spec requires a recent-activity section showing either:
    //   (a) a list of activity items (baseline creation, run execution, document generation), or
    //   (b) an empty-state message for a new account with no activity.

    // Collect candidates for the section heading / label
    const activitySection = page.getByText(/recent activity|activity feed/i).first();

    // Collect candidates for populated activity items
    const activityItems = page.locator(
      '[data-testid*="activity"], [class*="activity-item"], [class*="activityItem"]'
    );

    // Collect candidates for empty-state messages
    const emptyState = page.getByText(
      /no activity|no recent activity|nothing yet|get started|no actions yet/i
    );

    // Collect human-readable activity event text (inline fallback)
    const eventText = page.getByText(/baseline created|run executed|document generated/i).first();

    // Wait briefly for async content
    await page.waitForTimeout(2000);

    const sectionVisible = await activitySection.isVisible().catch(() => false);
    const itemCount = await activityItems.count().catch(() => 0);
    const emptyVisible = await emptyState.isVisible().catch(() => false);
    const eventVisible = await eventText.isVisible().catch(() => false);

    // At least one of the following must be true:
    // 1. The section heading/label is visible
    // 2. Activity items are rendered in the DOM
    // 3. An empty-state message is visible
    // 4. A recognisable activity event string is visible
    const activityPresent = sectionVisible || itemCount > 0 || emptyVisible || eventVisible;

    expect(
      activityPresent,
      `Expected a recent-activity section, activity items, or empty-state message on the dashboard. ` +
        `sectionVisible=${sectionVisible}, itemCount=${itemCount}, emptyVisible=${emptyVisible}, eventVisible=${eventVisible}`
    ).toBe(true);
  });
});
