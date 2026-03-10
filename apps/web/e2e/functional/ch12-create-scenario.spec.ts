import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch12 — Create Scenario', () => {
  test.beforeEach(async ({ page }) => {
    // Log in fresh before each test
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('clicking Create Scenario shows a form with name and description fields', async ({ page }) => {
    await page.goto(`${BASE}/scenarios`);
    await expect(page).toHaveURL(new RegExp('/scenarios'), { timeout: 10000 });

    // Find and click the Create Scenario / New scenario button
    const createButton = page.getByRole('button', { name: /create scenario|new scenario/i })
      .or(page.getByRole('link', { name: /create scenario|new scenario/i }));
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
    await createButton.first().click();

    // Wait for form to appear
    await page.waitForTimeout(1500);

    // Scroll down to ensure the form is in view
    await page.evaluate(() => window.scrollBy(0, 400));

    // Assert name/label field is visible — UI uses "Label" as the field name
    const nameField = page.getByLabel(/label/i)
      .or(page.locator('input[placeholder*="stress" i]'))
      .or(page.locator('input[placeholder*="case" i]'))
      .or(page.locator('input[placeholder*="downside" i]'))
      .or(page.getByRole('textbox', { name: /label|name/i }));
    await expect(nameField.first()).toBeVisible({ timeout: 10000 });

    // Assert description field is visible
    const descriptionField = page.getByLabel(/description/i)
      .or(page.locator('textarea[placeholder*="description" i]'))
      .or(page.locator('textarea[name="description"]'))
      .or(page.getByRole('textbox', { name: /description/i }));
    await expect(descriptionField.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Scenario form shows assumption override controls', async ({ page }) => {
    await page.goto(`${BASE}/scenarios`);
    await expect(page).toHaveURL(new RegExp('/scenarios'), { timeout: 10000 });

    // Find and click the Create Scenario button
    const createButton = page.getByRole('button', { name: /create scenario|new scenario/i })
      .or(page.getByRole('link', { name: /create scenario|new scenario/i }))
      .or(page.getByText(/create scenario/i).first());
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
    await createButton.first().click();

    // Wait for form to appear
    await page.waitForTimeout(1500);

    // Assert assumption override controls are available
    // Could be checkboxes, a list, a section heading, or input fields for overrides
    const assumptionControls = page
      .getByText(/assumption/i)
      .or(page.getByText(/override/i))
      .or(page.getByRole('checkbox'))
      .or(page.locator('[data-testid*="assumption"]'))
      .or(page.getByLabel(/assumption/i));

    await expect(assumptionControls.first()).toBeVisible({ timeout: 10000 });
  });
});
