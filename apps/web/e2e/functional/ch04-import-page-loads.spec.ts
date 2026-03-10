import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch04 — Import Excel Page Loads', () => {
  test('excel import page shows heading, stepper, and upload area after login', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /excel-import
    await page.goto(`${BASE}/excel-import`);

    // Assert page h1 heading contains 'Import Excel Model'
    await expect(page.locator('h1', { hasText: /import.*excel|excel.*import/i })).toBeVisible({ timeout: 10000 });

    // Assert stepper/progress bar is visible — the nav has aria-label="Import progress"
    await expect(page.getByRole('navigation', { name: /import progress/i })).toBeVisible({ timeout: 10000 });

    // Assert the Upload step label is visible in the stepper
    await expect(page.getByText('Upload').first()).toBeVisible({ timeout: 10000 });

    // Assert a file upload button is visible
    await expect(page.getByRole('button', { name: /select .xlsx file/i })).toBeVisible({ timeout: 10000 });
  });
});
