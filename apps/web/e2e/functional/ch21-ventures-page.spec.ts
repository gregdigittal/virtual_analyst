import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch21 — Ventures Page', () => {
  test('page heading contains Ventures or Startup', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    const heading = page.getByRole('heading').filter({ hasText: /ventures|startup/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create venture button is visible', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    const btn = page
      .getByRole('button', { name: /create venture|start|begin questionnaire/i })
      .or(page.getByRole('link', { name: /create venture|start|begin questionnaire/i }));
    await expect(btn.first()).toBeVisible({ timeout: 10000 });
  });

  test('wizard interface or new venture form is displayed', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    // Expect template ID or entity name input fields to be present (wizard form)
    const templateInput = page.getByRole('textbox', { name: /template/i });
    const entityInput = page.getByRole('textbox', { name: /entity|name/i });
    const anyFormField = templateInput.or(entityInput);
    await expect(anyFormField.first()).toBeVisible({ timeout: 10000 });
  });
});
