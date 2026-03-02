import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch04 — Import Upload Validation', () => {
  test('upload zone is visible with file input and select button', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /excel-import
    await page.goto(`${BASE}/excel-import`);

    // Assert the file upload action button is visible (the wizard uses a streaming approach
    // where file selection triggers upload directly — no separate "Next" button)
    const selectButton = page.getByRole('button', { name: /select .xlsx file/i })
      .or(page.getByRole('button', { name: /upload|browse|choose file/i }));
    await expect(selectButton.first()).toBeVisible({ timeout: 10000 });

    // Assert the hidden file input (click-to-browse) is present in the DOM
    await expect(page.locator('input[type="file"][accept=".xlsx"]')).toBeAttached({ timeout: 5000 });
  });
});
