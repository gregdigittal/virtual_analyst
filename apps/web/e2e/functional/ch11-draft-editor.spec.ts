import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch11 — Draft Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('draft editor workspace shows tabs and AI chat panel', async ({ page }) => {
    await page.goto(`${BASE}/drafts`);
    await expect(page).toHaveURL(new RegExp('/drafts'), { timeout: 10000 });

    // Wait for the page to load
    await page.waitForTimeout(2000);

    // Check if any draft exists in the list
    const draftLinks = page.locator('a[href^="/drafts/"]');
    const draftCount = await draftLinks.count();

    if (draftCount === 0) {
      // Try to create a new draft via the "New draft" button
      const newDraftBtn = page.getByRole('button', { name: /new draft/i }).first();
      const btnVisible = await newDraftBtn.isVisible();
      if (btnVisible) {
        await newDraftBtn.click();
        // Either navigates to draft or shows an error
        await page.waitForTimeout(3000);
        const currentUrl = page.url();
        if (!currentUrl.includes('/drafts/')) {
          // Could not create draft (e.g. no baseline) — fail
          const errorMsg = page.getByRole('alert');
          const errText = (await errorMsg.count()) > 0
            ? await errorMsg.first().textContent()
            : 'Could not navigate to draft editor';
          throw new Error(`No draft available and draft creation failed: ${errText}`);
        }
      } else {
        throw new Error('No drafts available and New draft button not visible');
      }
    } else {
      // Click the first draft to open the editor
      await draftLinks.first().click();
      await page.waitForURL((url) => /\/drafts\/[^/]+$/.test(url.pathname), { timeout: 10000 });
    }

    // Wait for draft editor content to load
    await page.waitForTimeout(2000);

    // Assert editor workspace tabs are visible (Overview tab)
    const overviewTab = page
      .getByRole('button', { name: /^overview$/i })
      .or(page.getByText(/^overview$/i));
    await expect(overviewTab.first()).toBeVisible({ timeout: 10000 });

    // Assert financial/assumption tabs exist (Revenue or Funding)
    const financialTab = page
      .getByRole('button', { name: /^revenue$/i })
      .or(page.getByText(/^revenue$/i))
      .or(page.getByRole('button', { name: /^funding$/i }))
      .or(page.getByText(/^funding$/i));
    await expect(financialTab.first()).toBeVisible({ timeout: 10000 });

    // Assert AI chat panel is visible — "Chat" heading
    const chatHeading = page.getByText(/^chat$/i);
    await expect(chatHeading.first()).toBeVisible({ timeout: 10000 });

    // Assert Send button is present in the chat panel
    const sendButton = page.getByRole('button', { name: /^send$/i });
    await expect(sendButton.first()).toBeVisible({ timeout: 10000 });
  });
});
