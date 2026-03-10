import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

async function login(page: import('@playwright/test').Page) {
  await page.goto(`${BASE}/login`);
  await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
}

test.describe('ch22 — Workflow Create', () => {
  test('Start workflow section is visible after navigating to /workflows', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // Wait for loading spinner to disappear
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading workflows'),
      { timeout: 15000 }
    );

    // The "Start workflow" section heading should be visible (this is the create-workflow section)
    const startSection = page.getByRole('heading', { name: /start workflow/i });
    await expect(startSection).toBeVisible({ timeout: 10000 });
  });

  test('template selection dropdown is available in the create workflow form', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading workflows'),
      { timeout: 15000 }
    );

    // Template label should be visible
    const templateLabel = page.getByText(/^template$/i);
    await expect(templateLabel.first()).toBeVisible({ timeout: 10000 });

    // Template select dropdown should be present (contains "Select template" option)
    const templateSelect = page.getByRole('combobox').filter({ hasText: /select template/i })
      .or(page.locator('select').filter({ hasText: /select template/i }));
    await expect(templateSelect.first()).toBeVisible({ timeout: 10000 });
  });

  test('entity binding controls exist with baseline, run, budget, and draft options', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading workflows'),
      { timeout: 15000 }
    );

    // Entity type label should be visible
    const entityTypeLabel = page.getByText(/entity type/i);
    await expect(entityTypeLabel.first()).toBeVisible({ timeout: 10000 });

    // Entity type select should be visible
    const entityTypeSelect = page.getByRole('combobox').filter({ hasText: /select type/i })
      .or(page.locator('select').filter({ hasText: /select type/i }));
    await expect(entityTypeSelect.first()).toBeVisible({ timeout: 10000 });

    // The entity type select should contain binding options for baseline, run, budget, draft
    const selectEl = page.locator('select').filter({ hasText: /select type/i });
    await expect(selectEl.first()).toBeVisible({ timeout: 10000 });

    // Verify entity type options exist — check option text in the select
    const optionBaseline = page.locator('select option[value="baseline"]');
    const optionRun = page.locator('select option[value="run"]');
    const optionBudget = page.locator('select option[value="budget"]');
    const optionDraft = page.locator('select option[value="draft"]');

    await expect(optionBaseline.first()).toBeAttached({ timeout: 10000 });
    await expect(optionRun.first()).toBeAttached({ timeout: 10000 });
    await expect(optionBudget.first()).toBeAttached({ timeout: 10000 });
    await expect(optionDraft.first()).toBeAttached({ timeout: 10000 });
  });

  test('Entity ID input and Start workflow button are present in the create form', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/workflows`);
    await expect(page).toHaveURL(`${BASE}/workflows`, { timeout: 10000 });

    // Wait for loading to complete
    await page.waitForFunction(
      () => !document.body.innerText.includes('Loading workflows'),
      { timeout: 15000 }
    );

    // Entity ID label should be visible
    const entityIdLabel = page.getByText(/entity id/i);
    await expect(entityIdLabel.first()).toBeVisible({ timeout: 10000 });

    // Entity ID input field (placeholder "e.g. bgt_xxx")
    const entityIdInput = page.getByPlaceholder(/bgt_/i);
    await expect(entityIdInput.first()).toBeVisible({ timeout: 10000 });

    // Start workflow submit button should be visible
    const startBtn = page.getByRole('button', { name: /start workflow/i });
    await expect(startBtn.first()).toBeVisible({ timeout: 10000 });
  });
});
