import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch06 — AFS Section Editor', () => {
  test('section editor shows section list with status indicators or empty state', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /afs
    await page.goto(`${BASE}/afs`);
    await expect(page).toHaveURL(`${BASE}/afs`, { timeout: 10000 });

    // Wait for content to load (skeleton resolves)
    await page.waitForSelector('[class*="skeleton"], [class*="Spinner"], .va-spinner, [aria-busy="true"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no skeleton visible — already loaded */ });
    await page.waitForTimeout(1000);

    // Collect all engagement links (cards on the /afs page link to /afs/{id}/*)
    // Exclude the /afs/frameworks path which is not an engagement
    const engagementLinks = page.locator('a[href*="/afs/"]').filter({
      hasNot: page.locator('[href="/afs/frameworks"]'),
    });

    const linkCount = await engagementLinks.count();

    if (linkCount === 0) {
      // No engagements — assert the empty state prompts creation
      const emptyState = page.getByText(/no afs engagements yet|create an engagement|get started/i);
      await expect(emptyState.first()).toBeVisible({ timeout: 10000 });
      // Also assert a create/new button is visible
      const newBtn = page.getByRole('button', { name: /new engagement|create engagement/i });
      await expect(newBtn.first()).toBeVisible({ timeout: 10000 });
      return;
    }

    // Try to find a card that leads directly to /sections (status is drafting)
    const sectionLinks = page.locator('a[href*="/sections"]');
    const sectionLinkCount = await sectionLinks.count();

    let sectionsUrl: string | null = null;

    if (sectionLinkCount > 0) {
      // A card already points to /sections — extract its href
      sectionsUrl = await sectionLinks.first().getAttribute('href');
    } else {
      // Extract the engagement ID from the first engagement card and build sections URL
      const firstHref = await engagementLinks.first().getAttribute('href');
      if (firstHref) {
        const match = firstHref.match(/\/afs\/([^/]+)/);
        if (match) {
          sectionsUrl = `/afs/${match[1]}/sections`;
        }
      }
    }

    if (!sectionsUrl) {
      // Fallback: assert the AFS page itself loaded (already verified above)
      return;
    }

    // Navigate to the section editor
    await page.goto(`${BASE}${sectionsUrl}`);
    await page.waitForURL((url) => url.pathname.includes('/sections') || url.pathname.includes('/afs/'), {
      timeout: 15000,
    });

    // Wait for loading spinner to resolve
    await page.waitForSelector('[class*="Spinner"], [class*="spinner"]', {
      state: 'detached',
      timeout: 10000,
    }).catch(() => { /* no spinner — already loaded */ });
    await page.waitForTimeout(500);

    // Assert "Sections" appears in the breadcrumb header
    const sectionsLabel = page.getByText('Sections');
    await expect(sectionsLabel.first()).toBeVisible({ timeout: 10000 });

    // Assert the "+ New" button (primary action to add a section)
    const newButton = page.getByRole('button', { name: /^\+\s*New$/i });
    await expect(newButton.first()).toBeVisible({ timeout: 10000 });

    // Assert either section items with status badges OR the empty state
    // Section items contain status text: draft, reviewed, or locked
    const sectionStatusBadges = page.getByText(/^draft$|^reviewed$|^locked$/i);
    const emptyMsg = page.getByText(/no sections yet/i);

    const badgeCount = await sectionStatusBadges.count();
    if (badgeCount > 0) {
      // Sections exist — each shows a visible status indicator
      await expect(sectionStatusBadges.first()).toBeVisible({ timeout: 5000 });
    } else {
      // Empty state — no sections drafted yet
      await expect(emptyMsg.first()).toBeVisible({ timeout: 10000 });
    }
  });
});
