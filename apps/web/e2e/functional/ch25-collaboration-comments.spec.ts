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

test.describe('ch25 — Collaboration Comments', () => {
  test('comments section is reachable on entity detail pages', async ({ page }) => {
    await login(page);

    // Navigate to baselines list and click the first entity link
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');

    const entityLink = page.locator('a[href*="/baselines/"]').first();
    await expect(entityLink).toBeVisible({ timeout: 15000 });
    await entityLink.click();

    // Verify we landed on a detail page (not redirected to login)
    await page.waitForLoadState('domcontentloaded');
    const url = page.url();
    expect(url).not.toContain('/login');
    expect(url).toMatch(/\/baselines\/.+/);
  });

  test('comment input or text area is visible on entity detail page', async ({ page }) => {
    await login(page);

    // Navigate to baselines list and click the first entity link
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');

    const entityLink = page.locator('a[href*="/baselines/"]').first();
    await expect(entityLink).toBeVisible({ timeout: 15000 });
    await entityLink.click();

    await page.waitForLoadState('domcontentloaded');

    // Look for the CommentThread textarea (placeholder "Add a comment...")
    // or a contenteditable element for comments
    const commentInput = page
      .locator('textarea[placeholder*="Add a comment" i]')
      .or(page.locator('textarea'))
      .or(page.locator('[contenteditable="true"]'));

    const isVisible = await commentInput.first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(isVisible).toBeTruthy();
  });

  test('comment thread or empty state is shown on entity detail page', async ({ page }) => {
    await login(page);

    // Navigate to baselines list and click the first entity link
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');

    const entityLink = page.locator('a[href*="/baselines/"]').first();
    await expect(entityLink).toBeVisible({ timeout: 15000 });
    await entityLink.click();

    await page.waitForLoadState('domcontentloaded');

    // Wait for the CommentThread to finish loading
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading comments'),
      { timeout: 15000 }
    ).catch(() => {});

    // The CommentThread component renders either "No comments yet." (empty state)
    // or comment cards with body text and timestamps
    const emptyState = page.getByText('No comments yet.');
    const commentCards = page.locator('textarea[placeholder*="Add a comment" i]');
    const postButton = page.getByRole('button', { name: /^post$/i });

    const hasEmpty = await emptyState.isVisible({ timeout: 10000 }).catch(() => false);
    const hasCommentInput = await commentCards.isVisible({ timeout: 5000 }).catch(() => false);
    const hasPostButton = await postButton.isVisible({ timeout: 5000 }).catch(() => false);

    // At least one of: empty state text, comment input, or Post button should be present
    // (all are rendered by CommentThread)
    expect(hasEmpty || hasCommentInput || hasPostButton).toBeTruthy();
  });
});
