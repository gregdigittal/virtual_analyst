import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch24 — Memos Page', () => {
  test('page heading contains Memo', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/memos`);
    await expect(page).toHaveURL(`${BASE}/memos`, { timeout: 10000 });

    const heading = page.getByRole('heading').filter({ hasText: /memo/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Memo button is visible', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/memos`);
    await expect(page).toHaveURL(`${BASE}/memos`, { timeout: 10000 });

    const btn = page
      .getByRole('button', { name: /create memo|new memo|generate memo/i })
      .or(page.getByRole('link', { name: /create memo|new memo|generate memo/i }));
    await expect(btn.first()).toBeVisible({ timeout: 10000 });
  });

  test('memo entries or empty state is shown', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/memos`);
    await expect(page).toHaveURL(`${BASE}/memos`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading'),
      { timeout: 10000 }
    );

    // Either a list of memos or an empty state is shown
    const listItem = page.locator('table, [role="list"], [role="listitem"]').first();
    const emptyState = page.getByText(/no memos|create your first|get started/i);

    const hasList = await listItem.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasList || hasEmpty).toBeTruthy();
  });
});
