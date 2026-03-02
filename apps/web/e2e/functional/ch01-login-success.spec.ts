import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch01 — Login Success', () => {
  test('valid credentials redirect to /dashboard', async ({ page }) => {
    await page.goto(`${BASE}/login`);

    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL(`${BASE}/baselines`, { timeout: 15000 });
  });
});
