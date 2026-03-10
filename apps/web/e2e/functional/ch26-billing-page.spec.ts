import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch26 — Billing Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('billing section is accessible from settings', async ({ page }) => {
    await page.goto(`${BASE}/settings`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Click the Billing nav link/tab if present, otherwise we may be on billing directly
    const billingLink = page.getByRole('link', { name: /billing/i });
    if (await billingLink.isVisible()) {
      await billingLink.click();
    } else {
      const billingTab = page.getByRole('tab', { name: /billing/i });
      if (await billingTab.isVisible()) {
        await billingTab.click();
      }
    }
    await expect(page.getByText(/billing/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('current plan tier is displayed', async ({ page }) => {
    await page.goto(`${BASE}/settings/billing`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Plan tier should show one of: Free, Starter, Pro, Enterprise, or similar
    const planText = page.getByText(/free|starter|pro|enterprise|plan/i);
    await expect(planText.first()).toBeVisible({ timeout: 15000 });
  });

  test('usage meters are visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/billing`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Usage meters for LLM tokens, Monte Carlo runs, or sync events
    const usageText = page.getByText(/usage|tokens?|monte carlo|sync|runs?/i);
    await expect(usageText.first()).toBeVisible({ timeout: 15000 });
  });

  test('plan upgrade or downgrade option exists', async ({ page }) => {
    await page.goto(`${BASE}/settings/billing`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    // Should have an upgrade, downgrade, or change plan button/link
    const changeOption = page.getByRole('button', { name: /upgrade|downgrade|change plan|manage/i })
      .or(page.getByRole('link', { name: /upgrade|downgrade|change plan|manage/i }))
      .or(page.getByText(/upgrade|downgrade|change plan/i));
    await expect(changeOption.first()).toBeVisible({ timeout: 15000 });
  });

  test('payment method section is visible', async ({ page }) => {
    await page.goto(`${BASE}/settings/billing`);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    const paymentText = page.getByText(/payment|card|billing method|invoice/i);
    await expect(paymentText.first()).toBeVisible({ timeout: 15000 });
  });
});
