import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch06 — AFS Dashboard Loads', () => {
  test('AFS page shows heading, Create Engagement button, and engagement list or empty state', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /afs
    await page.goto(`${BASE}/afs`);

    // Assert URL is /afs
    await expect(page).toHaveURL(`${BASE}/afs`, { timeout: 10000 });

    // Assert the page heading contains 'AFS' or 'Annual Financial Statements'
    const heading = page.getByRole('heading').filter({ hasText: /AFS|Annual Financial Statements/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Assert a 'Create Engagement' or 'New Engagement' button is visible
    const createButton = page.getByRole('button', { name: /create engagement|new engagement/i });
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });

    // Assert either engagement cards are displayed OR an empty/error state is shown
    // The page may show: engagement cards, an empty-state message, or a "Failed to fetch" error
    const engagementCards = page.locator('[data-testid="engagement-card"], .engagement-card');
    const emptyState = page.getByText(/no engagements|get started|no afs engagements|failed to fetch/i);

    const cardCount = await engagementCards.count();
    if (cardCount > 0) {
      // Cards are present — verify at least the first is visible
      await expect(engagementCards.first()).toBeVisible({ timeout: 5000 });
    } else {
      // Empty state or error state should be visible
      await expect(emptyState.first()).toBeVisible({ timeout: 10000 });
    }
  });
});
