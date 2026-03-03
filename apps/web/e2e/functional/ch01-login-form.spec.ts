import { test, expect } from '@playwright/test';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch01 — Login Form', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
  });

  test('email input field is visible', async ({ page }) => {
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
  });

  test('password input field is visible', async ({ page }) => {
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('Sign in button is visible', async ({ page }) => {
    await expect(
      page.getByRole('button', { name: /sign in/i }),
    ).toBeVisible();
  });

  test('Google SSO button is visible', async ({ page }) => {
    const google = page
      .getByRole('button', { name: /google/i })
      .or(page.getByRole('link', { name: /google/i }));
    await expect(google.first()).toBeVisible();
  });

  test('Microsoft SSO button is visible', async ({ page }) => {
    const microsoft = page
      .getByRole('button', { name: /microsoft/i })
      .or(page.getByRole('link', { name: /microsoft/i }));
    await expect(microsoft.first()).toBeVisible();
  });

  test('link to signup page exists', async ({ page }) => {
    const signupLink = page
      .getByRole('link', { name: /sign up/i })
      .or(page.getByRole('link', { name: /register/i }))
      .or(page.getByRole('link', { name: /create account/i }));
    await expect(signupLink.first()).toBeVisible();
  });
});
