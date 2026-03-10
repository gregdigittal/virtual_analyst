import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch23 — Board Packs List', () => {
  test('page heading contains Board Pack', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/board-packs`);
    await expect(page).toHaveURL(`${BASE}/board-packs`, { timeout: 10000 });

    const heading = page.getByRole('heading').filter({ hasText: /board pack/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Board Pack or New button is visible', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/board-packs`);
    await expect(page).toHaveURL(`${BASE}/board-packs`, { timeout: 10000 });

    const btn = page
      .getByRole('button', { name: /create board pack|new board pack|new/i })
      .or(page.getByRole('link', { name: /create board pack|new board pack|new/i }));
    await expect(btn.first()).toBeVisible({ timeout: 10000 });
  });

  test('board pack entries or empty state is shown', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/board-packs`);
    await expect(page).toHaveURL(`${BASE}/board-packs`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading'),
      { timeout: 10000 }
    );

    // Either a list of board packs or an empty state is shown
    const listItem = page.locator('table, [role="list"], [role="listitem"]').first();
    const emptyState = page.getByText(/no board packs|create your first|get started/i);

    const hasList = await listItem.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasList || hasEmpty).toBeTruthy();
  });
});
