import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch06 — AFS Create Engagement', () => {
  test('clicking Create Engagement opens a wizard with name and framework fields', async ({ page }) => {
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

    // Click the Create Engagement button
    const createButton = page.getByRole('button', { name: /create engagement|new engagement/i });
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
    await createButton.first().click();

    // Assert a wizard or modal/form appears
    const wizardOrForm = page.locator(
      '[role="dialog"], [role="form"], form, [data-testid*="wizard"], [data-testid*="modal"]'
    );
    // Also check for visible heading text that indicates a wizard/form opened
    const wizardHeading = page.getByText(
      /create engagement|new engagement|engagement details|setup wizard|engagement name|step 1/i
    );

    // Either a dialog/form container is visible, or a heading indicating the wizard opened
    const formVisible = await wizardOrForm.first().isVisible().catch(() => false);
    const headingVisible = await wizardHeading.first().isVisible().catch(() => false);
    expect(formVisible || headingVisible).toBe(true);

    // Assert engagement name field is present
    const nameField = page.getByRole('textbox', { name: /engagement name|name/i })
      .or(page.locator('input[name*="name"], input[placeholder*="name" i], input[id*="name"]'));
    await expect(nameField.first()).toBeVisible({ timeout: 10000 });

    // Assert framework selection field is present (IFRS / GAAP)
    const frameworkField = page
      .getByRole('combobox', { name: /framework/i })
      .or(page.getByRole('listbox', { name: /framework/i }))
      .or(page.getByText(/IFRS|GAAP/))
      .or(page.locator('select[name*="framework"], [data-testid*="framework"]'));
    await expect(frameworkField.first()).toBeVisible({ timeout: 10000 });
  });
});
