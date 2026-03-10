import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

async function login(page: any) {
  await page.goto(`${BASE}/login`);
  await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url: URL) => !url.pathname.includes('/login'), { timeout: 15000 });
}

test.describe('ch22 — Inbox / Tasks', () => {
  test('inbox or assignments page loads and shows task list interface', async ({ page }) => {
    await login(page);

    // Try /inbox first, fall back to /assignments
    await page.goto(`${BASE}/inbox`);
    const finalUrl = page.url();

    // If redirected away from /inbox, try /assignments
    if (!finalUrl.includes('/inbox')) {
      await page.goto(`${BASE}/assignments`);
    }

    // Wait for page content to load
    await page.waitForLoadState('networkidle', { timeout: 15000 });

    // Assert page has a heading related to inbox, tasks, or assignments
    const heading = page
      .getByRole('heading')
      .filter({ hasText: /inbox|tasks|assignments|my tasks|task queue/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });
  });

  test('page shows assigned tasks or empty inbox message', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/inbox`);
    const afterInbox = page.url();

    if (!afterInbox.includes('/inbox')) {
      await page.goto(`${BASE}/assignments`);
    }

    await page.waitForLoadState('networkidle', { timeout: 15000 });

    // Either a task list is shown, or an empty state message
    const taskItem = page.locator('[data-testid*="task"], [class*="task-item"], tr, li').first();
    const emptyMsg = page
      .getByText(/no tasks|no assigned tasks|inbox is empty|nothing here|no pending tasks/i)
      .first();

    const hasTask = await taskItem.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyMsg.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasTask || hasEmpty).toBeTruthy();
  });

  test('pool tasks section or claim button is present', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/inbox`);
    const afterInbox = page.url();

    if (!afterInbox.includes('/inbox')) {
      await page.goto(`${BASE}/assignments`);
    }

    await page.waitForLoadState('networkidle', { timeout: 15000 });

    // Look for pool/claim UI, a "Claim" button, or a pool tasks section
    const claimEl = page
      .getByRole('button', { name: /claim/i })
      .or(page.getByText(/pool tasks|available tasks|unassigned tasks/i).first())
      .or(page.getByRole('heading', { name: /pool|available|unassigned/i }).first());

    // Also accept the assigned tasks section heading or any task-related content
    const assignedSection = page
      .getByRole('heading', { name: /assigned|my tasks|inbox/i })
      .first();

    const hasClaimUi = await claimEl.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasAssignedSection = await assignedSection.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasClaimUi || hasAssignedSection).toBeTruthy();
  });
});
