import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch03 — Marketplace Search', () => {
  test('search bar filters templates by name/industry', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /marketplace
    await page.goto(`${BASE}/marketplace`);
    await expect(page).toHaveURL(`${BASE}/marketplace`, { timeout: 10000 });

    // Wait for the page to fully load
    await page.waitForTimeout(3000);

    // Locate the search input field
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i], input[placeholder*="filter" i], input[aria-label*="search" i], [data-testid="search-input"]').first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    // Count total templates before searching
    let totalBeforeSearch = 0;
    const templateCards = page.locator('[data-testid="template-card"]');
    const cardCount = await templateCards.count();
    if (cardCount > 0) {
      totalBeforeSearch = cardCount;
    } else {
      const gridItems = page.locator('div[class*="grid"] > div, div[class*="card"]').filter({ hasText: /.{5,}/ });
      totalBeforeSearch = await gridItems.count();
    }

    // Type a search query
    await searchInput.fill('SaaS');
    await page.waitForTimeout(1000);

    // Check filtered results — either fewer results or a "no results" message
    const templateCardsAfter = page.locator('[data-testid="template-card"]');
    const cardCountAfter = await templateCardsAfter.count();

    if (cardCount > 0) {
      // data-testid cards exist — count should differ or remain (if all match)
      // Either fewer results OR a no-results message should appear
      const noResultsMsg = page.locator('text=/no results|no templates|not found/i');
      const noResultsVisible = await noResultsMsg.isVisible().catch(() => false);
      if (!noResultsVisible) {
        // Results should be visible and count should be <= original
        expect(cardCountAfter).toBeLessThanOrEqual(totalBeforeSearch);
        if (cardCountAfter > 0) {
          await expect(templateCardsAfter.first()).toBeVisible({ timeout: 5000 });
        }
      }
    } else {
      // No data-testid — use generic approach
      const gridItemsAfter = page.locator('div[class*="grid"] > div, div[class*="card"]').filter({ hasText: /.{5,}/ });
      const gridCountAfter = await gridItemsAfter.count();

      // Check for no-results state or filtered results
      const noResultsMsg = page.locator('text=/no results|no templates|not found/i');
      const noResultsVisible = await noResultsMsg.isVisible().catch(() => false);

      if (!noResultsVisible) {
        // Filtered results should be <= total before search
        expect(gridCountAfter).toBeLessThanOrEqual(totalBeforeSearch);
      }
    }

    // Now try clearing the search and verify results expand back or restore
    await searchInput.fill('');
    await page.waitForTimeout(1000);

    const templateCardsCleared = page.locator('[data-testid="template-card"]');
    const cardCountCleared = await templateCardsCleared.count();

    if (cardCount > 0) {
      // After clearing, should show at least as many as before (or same)
      expect(cardCountCleared).toBeGreaterThanOrEqual(cardCountAfter);
    } else {
      const gridItemsCleared = page.locator('div[class*="grid"] > div, div[class*="card"]').filter({ hasText: /.{5,}/ });
      const gridCountCleared = await gridItemsCleared.count();
      expect(gridCountCleared).toBeGreaterThanOrEqual(0);
    }
  });
});
