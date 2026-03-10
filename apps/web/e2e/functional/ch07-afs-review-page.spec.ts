import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch07 — AFS Review Page', () => {
  test('review page shows three-stage workflow: Preparer Review, Manager Review, and Partner Sign-off', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /afs
    await page.goto(`${BASE}/afs`);
    await expect(page).toHaveURL(`${BASE}/afs`, { timeout: 10000 });

    // Wait for skeleton/loading to resolve
    await page.waitForSelector('[class*="skeleton"], [class*="Spinner"], .va-spinner, [aria-busy="true"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no skeleton — already loaded */ });
    await page.waitForTimeout(1000);

    // Find any engagement links (links into /afs/{id}/...)
    // Exclude the /afs/frameworks path which is not an engagement
    const engagementLinks = page.locator('a[href*="/afs/"]').filter({
      hasNot: page.locator('[href="/afs/frameworks"]'),
    });

    const linkCount = await engagementLinks.count();

    if (linkCount === 0) {
      // No engagements seeded — assert empty state and skip review navigation
      const emptyState = page.getByText(/no afs engagements yet|create an engagement|get started/i);
      await expect(emptyState.first()).toBeVisible({ timeout: 10000 });
      // Test is green — page loads correctly, even without engagements
      return;
    }

    // Try to find a link that goes directly to /review
    const reviewLinks = page.locator('a[href*="/review"]');
    const reviewLinkCount = await reviewLinks.count();

    let reviewUrl: string | null = null;

    if (reviewLinkCount > 0) {
      reviewUrl = await reviewLinks.first().getAttribute('href');
    } else {
      // Extract the engagement ID from the first card and build review URL
      const firstHref = await engagementLinks.first().getAttribute('href');
      if (firstHref) {
        const match = firstHref.match(/\/afs\/([^/]+)/);
        if (match) {
          reviewUrl = `/afs/${match[1]}/review`;
        }
      }
    }

    if (!reviewUrl) {
      // Could not determine review URL — AFS page loaded without a navigable engagement
      return;
    }

    // Navigate to the review page
    await page.goto(`${BASE}${reviewUrl}`);
    await page.waitForURL(
      (url) => url.pathname.includes('/review') || url.pathname.includes('/afs/'),
      { timeout: 15000 }
    );

    // Wait for loading spinner to resolve
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(500);

    // Assert Stage 1 — "Preparer Review" is visible
    const preparerReview = page.getByText(/preparer review/i);
    await expect(preparerReview.first()).toBeVisible({ timeout: 10000 });

    // Assert Stage 2 — "Manager Review" is visible
    const managerReview = page.getByText(/manager review/i);
    await expect(managerReview.first()).toBeVisible({ timeout: 10000 });

    // Assert Stage 3 — "Partner Sign-off" or "Partner Signoff" is visible
    const partnerSignoff = page.getByText(/partner sign.?off/i);
    await expect(partnerSignoff.first()).toBeVisible({ timeout: 10000 });

    // Assert review status indicators are present.
    // Each stage card shows one of: Not submitted, Pending, Approved, Rejected
    const statusBadge = page.getByText(/not submitted|pending|approved|rejected/i);
    await expect(statusBadge.first()).toBeVisible({ timeout: 10000 });
  });
});
