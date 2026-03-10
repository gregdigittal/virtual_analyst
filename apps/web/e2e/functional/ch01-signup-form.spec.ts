import { test, expect } from '@playwright/test';

test.describe('ch01 — Signup Form', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/signup');
  });

  test('email input field is visible', async ({ page }) => {
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
  });

  test('password input field is visible', async ({ page }) => {
    await expect(page.locator('input[type="password"]').first()).toBeVisible();
  });

  test('confirm password input field is visible', async ({ page }) => {
    await expect(page.locator('input[type="password"]')).toHaveCount(2);
  });

  test('Create account or Sign up button is visible', async ({ page }) => {
    const submitBtn = page
      .getByRole('button', { name: /create account/i })
      .or(page.getByRole('button', { name: /sign up/i }));
    await expect(submitBtn.first()).toBeVisible();
  });

  test('Google OAuth button is visible', async ({ page }) => {
    const google = page
      .getByRole('button', { name: /google/i })
      .or(page.getByRole('link', { name: /google/i }));
    await expect(google.first()).toBeVisible();
  });

  test('Microsoft OAuth button is visible', async ({ page }) => {
    const microsoft = page
      .getByRole('button', { name: /microsoft/i })
      .or(page.getByRole('link', { name: /microsoft/i }));
    await expect(microsoft.first()).toBeVisible();
  });
});
