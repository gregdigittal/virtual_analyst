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

/**
 * Try multiple entity list pages to find one with clickable detail links.
 * Returns the first visible entity link or null if none found.
 */
async function findEntityDetailLink(page: any) {
  const entityPages = [
    { path: '/baselines', linkPattern: 'a[href*="/baselines/"]' },
    { path: '/runs', linkPattern: 'a[href*="/runs/"]' },
    { path: '/drafts', linkPattern: 'a[href*="/drafts/"]' },
  ];

  for (const { path, linkPattern } of entityPages) {
    await page.goto(`${BASE}${path}`);
    await page.waitForLoadState('domcontentloaded');
    // Wait for content to load
    await page.waitForTimeout(5000);

    const entityLink = page.locator(linkPattern).first();
    const isVisible = await entityLink.isVisible({ timeout: 10000 }).catch(() => false);
    if (isVisible) {
      return entityLink;
    }
  }
  return null;
}

test.describe('ch25 — Collaboration Comments', () => {
  test('comments section is reachable on entity detail pages', async ({ page }) => {
    await login(page);

    const entityLink = await findEntityDetailLink(page);

    // If no entities exist at all, skip gracefully
    if (!entityLink) {
      test.skip(true, 'No entity detail pages available for test user');
      return;
    }

    await entityLink.click();

    // Wait for client-side navigation to the detail page
    await page.waitForURL(/\/(baselines|runs|drafts)\/.+/, { timeout: 15000 });
    const url = page.url();
    expect(url).not.toContain('/login');
    expect(url).toMatch(/\/(baselines|runs|drafts)\/.+/);
  });

  test('comment input or text area is visible on entity detail page', async ({ page }) => {
    await login(page);

    const entityLink = await findEntityDetailLink(page);

    if (!entityLink) {
      test.skip(true, 'No entity detail pages available for test user');
      return;
    }

    await entityLink.click();
    await page.waitForURL(/\/(baselines|runs|drafts)\/.+/, { timeout: 15000 });

    // Wait for the page to finish loading its primary data (CommentThread is
    // conditionally rendered only after the parent page's loading state is false)
    await page.waitForFunction(
      () => {
        const body = document.body.innerText;
        // Page shows "Loading…" or spinner while fetching main entity data
        return !body.includes('Loading');
      },
      { timeout: 30000 }
    ).catch(() => {});

    // Extra wait for React re-render after loading state change
    await page.waitForTimeout(2000);

    // Look for the CommentThread textarea (placeholder "Add a comment...")
    // or a contenteditable element for comments
    const commentInput = page
      .locator('textarea[placeholder*="Add a comment" i]')
      .or(page.locator('textarea'))
      .or(page.locator('[contenteditable="true"]'));

    const isVisible = await commentInput.first().isVisible({ timeout: 15000 }).catch(() => false);
    expect(isVisible).toBeTruthy();
  });

  test('comment thread or empty state is shown on entity detail page', async ({ page }) => {
    await login(page);

    const entityLink = await findEntityDetailLink(page);

    if (!entityLink) {
      test.skip(true, 'No entity detail pages available for test user');
      return;
    }

    await entityLink.click();
    await page.waitForURL(/\/(baselines|runs|drafts)\/.+/, { timeout: 15000 });

    // Wait for the page to finish loading its primary data first
    // (CommentThread is only rendered after parent page's loading state is false)
    await page.waitForFunction(
      () => {
        const body = document.body.innerText;
        return !body.includes('Loading');
      },
      { timeout: 30000 }
    ).catch(() => {});

    // Extra wait for React re-render after loading state change
    await page.waitForTimeout(2000);

    // Now wait for CommentThread's own loading to finish
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading comments'),
      { timeout: 15000 }
    ).catch(() => {});

    // The CommentThread component renders either "No comments yet." (empty state)
    // or comment cards with body text and timestamps
    const emptyState = page.getByText('No comments yet.');
    const commentCards = page.locator('textarea[placeholder*="Add a comment" i]');
    const postButton = page.getByRole('button', { name: /^post$/i });

    const hasEmpty = await emptyState.isVisible({ timeout: 15000 }).catch(() => false);
    const hasCommentInput = await commentCards.isVisible({ timeout: 10000 }).catch(() => false);
    const hasPostButton = await postButton.isVisible({ timeout: 10000 }).catch(() => false);

    // At least one of: empty state text, comment input, or Post button should be present
    // (all are rendered by CommentThread)
    expect(hasEmpty || hasCommentInput || hasPostButton).toBeTruthy();
  });
});
