import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch03 — Marketplace Loads', () => {
  test('marketplace page shows heading and template cards', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /marketplace
    await page.goto(`${BASE}/marketplace`);

    // Assert the page URL is /marketplace
    await expect(page).toHaveURL(`${BASE}/marketplace`, { timeout: 10000 });

    // Assert the page heading contains 'Marketplace' or 'Templates'
    const heading = page.getByRole('heading', { name: /marketplace|templates/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Wait for content to load
    await page.waitForTimeout(3000);

    // Assert at least one template card is visible
    // Cards are rendered as div-based grid items; look for any element with a name and type badge
    const templateCards = page.locator('[data-testid="template-card"]');
    const cardCount = await templateCards.count();

    if (cardCount > 0) {
      // Assert the first card shows a name (non-empty text)
      await expect(templateCards.first()).toBeVisible({ timeout: 5000 });
      const cardText = await templateCards.first().textContent();
      expect(cardText?.trim().length).toBeGreaterThan(0);
    } else {
      // No data-testid cards — try generic grid/card elements
      const gridItems = page.locator('div[class*="grid"] > div, div[class*="card"]').filter({ hasText: /.{3,}/ });
      const gridCount = await gridItems.count();
      // This assertion will fail if no cards are present, correctly marking as RED
      expect(gridCount).toBeGreaterThan(0);
      await expect(gridItems.first()).toBeVisible({ timeout: 5000 });
    }
  });
});
