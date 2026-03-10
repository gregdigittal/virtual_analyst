import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch09 — Create Org Group', () => {
  test('clicking Create New opens a group creation form with a group name field', async ({ page }) => {
    // Log in fresh
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for login to complete
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to /org-structures
    await page.goto(`${BASE}/org-structures`);
    await expect(page).toHaveURL(new RegExp('/org-structures'), { timeout: 10000 });

    // Click the Create New / Create Group button
    const createButton = page
      .getByRole('button', { name: /create new|create group|new group|add group/i })
      .or(page.getByRole('link', { name: /create new|create group|new group|add group/i }));
    await expect(createButton.first()).toBeVisible({ timeout: 10000 });
    await createButton.first().click();

    // Assert a form / heading appears indicating group creation
    const formOrHeading = page
      .getByRole('heading', { name: /new group structure|create group|group details/i })
      .or(page.getByText(/new group structure|create group|group details/i));
    await expect(formOrHeading.first()).toBeVisible({ timeout: 10000 });

    // Assert group name field is present
    const nameField = page.getByRole('textbox', { name: /group name/i })
      .or(page.locator('input[name*="name"], input[placeholder*="group" i]'));
    await expect(nameField.first()).toBeVisible({ timeout: 10000 });

    // Assert entity-related controls or content exist on the page.
    // The user manual states the form sets up a group that organises entities.
    // Either an "Add Entity" control is present, or the page references entities
    // (e.g. empty-state text "organize your entities") confirming entity management is here.
    const entityControls = page
      .getByRole('button', { name: /add entity/i })
      .or(page.getByRole('tab', { name: /entities/i }))
      .or(page.getByText(/entities|organize your entities|add entity/i));
    await expect(entityControls.first()).toBeVisible({ timeout: 10000 });
  });
});
