import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch05 — Create Connection Form', () => {
  test('create connection form shows name, target, and mode fields', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete (redirects away from /login)
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /excel-connections
    await page.goto(`${BASE}/excel-connections`);

    // Wait for page heading to appear
    await expect(page.getByRole('heading', { level: 1, name: /excel connections/i })).toBeVisible({
      timeout: 15000,
    });

    // The "Create connection" form is inline — assert its section heading is visible
    await expect(page.getByRole('heading', { level: 2, name: /create connection/i })).toBeVisible({
      timeout: 10000,
    });

    // Assert the connection name (Label) field is present
    await expect(page.getByPlaceholder('Label')).toBeVisible({ timeout: 10000 });

    // Assert mode selection (Read-only / Read-write) combobox is present
    const modeSelect = page.getByRole('combobox');
    await expect(modeSelect).toBeVisible({ timeout: 10000 });

    // Assert Read-only and Read-write options exist in the combobox
    await expect(modeSelect.locator('option', { hasText: /read.only/i })).toHaveCount(1);
    await expect(modeSelect.locator('option', { hasText: /read.write/i })).toHaveCount(1);

    // Assert target JSON textarea is visible (contains baseline_id / run_id keys)
    const targetTextarea = page.locator('textarea').filter({ hasText: /baseline_id|run_id/ });
    await expect(targetTextarea).toBeVisible({ timeout: 10000 });

    // Assert the Create connection submit button is visible
    await expect(
      page.getByRole('button', { name: /create connection/i })
    ).toBeVisible({ timeout: 10000 });
  });
});
