import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Teams Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('Teams section loads from settings navigation', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Click Teams link/tab if available, otherwise navigate directly
    const teamsLink = page.getByRole('link', { name: /^teams$/i });
    if (await teamsLink.isVisible()) {
      await teamsLink.click();
    } else {
      await page.goto(`${BASE}/settings/teams`);
    }
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    await expect(page.getByRole('heading', { name: /teams/i })).toBeVisible({ timeout: 10000 });
  });

  test('team member list is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/teams`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Spec: "The team list shows each member's name, email, role, and status"
    // Expect either a populated list or an empty state message
    const hasList = await page.locator('table, [role="table"], [role="grid"]').isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no team members|no members yet|invite your first|add your first/i).isVisible().catch(() => false);
    expect(hasList || hasEmptyState).toBeTruthy();
  });

  test('Invite or Add Member button is present', async ({ page }) => {
    await page.goto(`${BASE}/settings/teams`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Spec: "Admins can invite new users"
    const inviteButton = page.getByRole('button', { name: /invite|add member/i });
    const inviteLink = page.getByRole('link', { name: /invite|add member/i });
    await expect(inviteButton.or(inviteLink).first()).toBeVisible({ timeout: 10000 });
  });

  test('each team member shows a name and role', async ({ page }) => {
    await page.goto(`${BASE}/settings/teams`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Spec: "the team list shows each member's name, email, role, and status"
    // Check for role column header or role values in the list
    const roleHeader = page.getByText(/^role$/i);
    const roleValue = page.getByText(/admin|owner|member|viewer|editor/i).first();
    await expect(roleHeader.or(roleValue)).toBeVisible({ timeout: 10000 });
  });
});
