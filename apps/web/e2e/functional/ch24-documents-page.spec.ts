import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch24 — Documents Page', () => {
  test('page heading contains Documents', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/documents`);
    await expect(page).toHaveURL(`${BASE}/documents`, { timeout: 10000 });

    const heading = page.getByRole('heading').filter({ hasText: /documents/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('search or filter input is visible', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/documents`);
    await expect(page).toHaveURL(`${BASE}/documents`, { timeout: 10000 });

    const searchOrFilter = page
      .getByRole('searchbox')
      .or(page.getByRole('textbox', { name: /search|filter|entity/i }))
      .or(page.locator('input[placeholder*="search" i]'))
      .or(page.locator('input[placeholder*="filter" i]'))
      .or(page.locator('input[placeholder*="entity" i]'))
      .or(page.getByRole('combobox'))
      .or(page.locator('select'));

    await expect(searchOrFilter.first()).toBeVisible({ timeout: 10000 });
  });

  test('document entries or empty state is shown', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/documents`);
    await expect(page).toHaveURL(`${BASE}/documents`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading'),
      { timeout: 10000 }
    );

    // Either document entries or an empty state is shown
    const listItem = page.locator('table, [role="list"], [role="listitem"], [role="row"]').first();
    const emptyState = page.getByText(/no documents|no files|no outputs|get started|nothing here/i);

    const hasList = await listItem.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasList || hasEmpty).toBeTruthy();
  });
});
