import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch09 — Org Structures Page', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('org structures page heading contains Group, Organization, or Structure', async ({ page }) => {
    await page.goto(`${BASE}/org-structures`);
    await expect(page).toHaveURL(new RegExp('/org-structures'), { timeout: 10000 });

    // Heading must contain one of the expected keywords
    const heading = page.getByRole('heading', { name: /group|organization|structure/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('org structures page shows a Create Group or Add Entity button', async ({ page }) => {
    await page.goto(`${BASE}/org-structures`);

    const btn = page
      .getByRole('button', { name: /create group|add entity|new group|add group/i })
      .or(page.getByRole('link', { name: /create group|add entity|new group|add group/i }));
    await expect(btn.first()).toBeVisible({ timeout: 10000 });
  });

  test('org structures page shows a hierarchy view or empty state', async ({ page }) => {
    await page.goto(`${BASE}/org-structures`);

    // Either a hierarchy/tree/list of groups OR an empty-state message is shown
    const hierarchyOrEmpty = page
      .getByRole('list')
      .or(page.getByRole('tree'))
      .or(page.getByRole('table'))
      .or(page.getByText(/no groups|no entities|no organizations|empty|get started|create your first/i));
    await expect(hierarchyOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });
});
