import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch11 — Draft Commit', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  async function openDraft(page: any) {
    await page.goto(`${BASE}/drafts`);
    await expect(page).toHaveURL(new RegExp('/drafts'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    const draftLinks = page.locator('a[href^="/drafts/"]');
    const draftCount = await draftLinks.count();

    if (draftCount === 0) {
      const newDraftBtn = page.getByRole('button', { name: /new draft/i }).first();
      const btnVisible = await newDraftBtn.isVisible();
      if (btnVisible) {
        await newDraftBtn.click();
        await page.waitForTimeout(3000);
        const currentUrl = page.url();
        if (!currentUrl.includes('/drafts/')) {
          throw new Error('Could not navigate to draft editor after clicking New Draft');
        }
      } else {
        throw new Error('No drafts available and New Draft button not visible');
      }
    } else {
      await draftLinks.first().click();
      await page.waitForURL((url) => /\/drafts\/[^/]+$/.test(url.pathname), { timeout: 10000 });
    }

    await page.waitForTimeout(2000);
  }

  test('Commit or Mark Ready button is visible in draft editor', async ({ page }) => {
    await openDraft(page);

    // The spec says the draft editor has a Commit Draft button or Mark Ready button
    // per the user manual: "Mark Ready" transitions to ready_to_commit, then "Commit Draft" finalizes
    const commitButton = page
      .getByRole('button', { name: /commit draft/i })
      .or(page.getByRole('button', { name: /commit/i }))
      .or(page.getByRole('button', { name: /mark ready/i })
        .or(page.getByRole('button', { name: /save as baseline/i })));

    await expect(commitButton.first()).toBeVisible({ timeout: 10000 });
  });

  test('integrity check indicators (errors/warnings) are shown in draft editor', async ({ page }) => {
    await openDraft(page);

    // According to the spec: integrity check indicators show errors and/or warnings
    // The user manual says "Run Integrity Checks" triggers validation checks
    // After running checks, error/warning indicators appear in the editor

    // First look for the Run Integrity Checks button
    const runChecksBtn = page
      .getByRole('button', { name: /run integrity checks/i })
      .or(page.getByRole('button', { name: /integrity check/i }))
      .or(page.getByText(/integrity checks/i));

    const checksVisible = await runChecksBtn.first().isVisible().catch(() => false);

    if (checksVisible) {
      // Click to run the checks if the button is present
      const btn = page.getByRole('button', { name: /run integrity checks/i })
        .or(page.getByRole('button', { name: /integrity check/i }));
      const btnVisible = await btn.first().isVisible().catch(() => false);
      if (btnVisible) {
        await btn.first().click();
        await page.waitForTimeout(3000);
      }
    }

    // After running (or if checks are auto-run), look for integrity indicators:
    // - "Errors" or "Warnings" counts/badges
    // - An integrity report section
    // - "passed" / "error" / "warning" labels
    const integrityIndicator = page
      .getByText(/errors?/i)
      .or(page.getByText(/warnings?/i))
      .or(page.getByText(/integrity/i))
      .or(page.getByText(/checks? passed/i))
      .or(page.getByText(/check result/i))
      .or(page.getByText(/validation/i));

    await expect(integrityIndicator.first()).toBeVisible({ timeout: 10000 });
  });
});
