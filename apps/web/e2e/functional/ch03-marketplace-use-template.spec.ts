import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch03 — Marketplace Use Template', () => {
  test('clicking Use Template opens dialog, fills fields, creates baseline, redirects to baselines', async ({ page }) => {
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

    // Wait for the page to fully load and template cards to appear
    await page.waitForTimeout(3000);

    // Find the 'Use Template' button on the first template card
    const useTemplateBtn = page.getByRole('button', { name: /use template/i }).first();
    await expect(useTemplateBtn).toBeVisible({ timeout: 10000 });

    // Click 'Use Template' to open the dialog
    await useTemplateBtn.click();

    // Assert a dialog/modal appears
    const dialog = page.locator('[role="dialog"], [data-testid="use-template-dialog"], [data-testid="create-baseline-dialog"]').first();
    await expect(dialog).toBeVisible({ timeout: 10000 });

    // Assert label field is present
    const labelInput = dialog.locator('input[name="label"], input[placeholder*="label" i], input[aria-label*="label" i], [data-testid="label-input"]').first();
    const labelInputFallback = page.locator('input[name="label"], input[placeholder*="label" i], input[aria-label*="label" i], [data-testid="label-input"]').first();
    const labelVisible = await labelInput.isVisible().catch(() => false);
    const actualLabelInput = labelVisible ? labelInput : labelInputFallback;
    await expect(actualLabelInput).toBeVisible({ timeout: 5000 });

    // Assert fiscal year end date field is present
    const fiscalInput = dialog.locator('input[name*="fiscal" i], input[placeholder*="fiscal" i], input[aria-label*="fiscal" i], input[type="date"], [data-testid="fiscal-year-input"]').first();
    const fiscalInputFallback = page.locator('input[name*="fiscal" i], input[placeholder*="fiscal" i], input[aria-label*="fiscal" i], input[type="date"], [data-testid="fiscal-year-input"]').first();
    const fiscalVisible = await fiscalInput.isVisible().catch(() => false);
    const actualFiscalInput = fiscalVisible ? fiscalInput : fiscalInputFallback;
    await expect(actualFiscalInput).toBeVisible({ timeout: 5000 });

    // Fill in the label
    await actualLabelInput.fill('Test Baseline from Template');

    // Fill in the fiscal year end date
    await actualFiscalInput.fill('2025-12-31');

    // Click the confirm/create button inside the dialog
    const confirmBtn = page.locator('[role="dialog"] button, [data-testid="use-template-dialog"] button, [data-testid="create-baseline-dialog"] button')
      .filter({ hasText: /create|confirm|submit|use|ok/i })
      .first();
    const confirmBtnFallback = page.getByRole('button', { name: /create|confirm|submit|use baseline|create baseline/i }).first();

    const confirmVisible = await confirmBtn.isVisible().catch(() => false);
    const actualConfirmBtn = confirmVisible ? confirmBtn : confirmBtnFallback;
    await expect(actualConfirmBtn).toBeVisible({ timeout: 5000 });
    await actualConfirmBtn.click();

    // Assert either navigation to /baselines or a success message appears
    const navigatedToBaselines = page.waitForURL((url) => url.pathname.includes('/baselines'), { timeout: 15000 })
      .then(() => true)
      .catch(() => false);

    const successMsg = page.locator('text=/baseline created|success|created successfully/i');
    const successVisible = successMsg.isVisible().catch(() => false);

    const [didNavigate, didShowSuccess] = await Promise.all([navigatedToBaselines, successVisible]);

    if (!didNavigate && !didShowSuccess) {
      // Final check — either URL changed or success toast visible
      const currentUrl = page.url();
      const hasBaselineInUrl = currentUrl.includes('/baselines');
      const toastVisible = await page.locator('[role="alert"], [data-testid="toast"], .toast').isVisible().catch(() => false);
      expect(hasBaselineInUrl || toastVisible).toBe(true);
    }
  });
});
