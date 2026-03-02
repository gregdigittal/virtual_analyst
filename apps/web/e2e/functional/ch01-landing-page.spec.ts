import { test, expect } from '@playwright/test';

test.describe('ch01 — Landing Page', () => {
  test('hero heading is visible', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByRole('heading', { name: /One Platform for the Full Financial Modeling Workflow/i }),
    ).toBeVisible();
  });

  test('CTA button with "Get started" text is visible', async ({ page }) => {
    await page.goto('/');
    const cta = page.getByRole('link', { name: /get started/i }).or(
      page.getByRole('button', { name: /get started/i }),
    );
    await expect(cta.first()).toBeVisible();
  });

  test('clicking CTA navigates to auth page', async ({ page }) => {
    await page.goto('/');
    const cta = page.getByRole('link', { name: /get started/i }).or(
      page.getByRole('button', { name: /get started/i }),
    );
    await cta.first().click();
    await expect(page).toHaveURL(/\/(login|signup|auth)/);
  });
});
