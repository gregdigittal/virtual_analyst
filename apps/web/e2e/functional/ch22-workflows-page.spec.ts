import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch22 — Workflows Page', () => {
  test('page heading contains Workflows', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    const heading = page.getByRole('heading').filter({ hasText: /workflows/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Workflow or Start Workflow button is visible', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // The page uses "Start workflow" as the action button
    const btn = page
      .getByRole('button', { name: /create workflow|new workflow|start workflow/i })
      .or(page.getByRole('link', { name: /create workflow|new workflow|start workflow/i }));
    await expect(btn.first()).toBeVisible({ timeout: 10000 });
  });

  test('workflow instances or empty state is shown', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // Wait for page to finish loading (loading spinner disappears)
    await page.waitForFunction(() => !document.body.innerText.includes('Loading workflows'), { timeout: 10000 });

    // Either a list of workflow instances or an empty state heading is shown
    const instancesHeading = page.getByRole('heading', { name: /instances/i });
    const emptyState = page.getByRole('heading', { name: /no workflow instances|no instances/i });

    const hasInstancesSection = await instancesHeading.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmptyState = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasInstancesSection || hasEmptyState).toBeTruthy();
  });
});
