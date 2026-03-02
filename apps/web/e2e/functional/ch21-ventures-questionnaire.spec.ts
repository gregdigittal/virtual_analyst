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

async function selectTemplate(page: import('@playwright/test').Page) {
  // Select the first available template from the dropdown
  const templateSelect = page.locator('select[aria-label="Template"]');
  await templateSelect.waitFor({ state: 'visible', timeout: 10000 });
  const options = await templateSelect.locator('option:not([disabled])').allTextContents();
  if (options.length > 0) {
    await templateSelect.selectOption({ index: 1 }); // First non-disabled option
  }
}

test.describe('ch21 — Ventures Questionnaire', () => {
  test('questionnaire question fields appear after creating a venture', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    // Fill in the new venture form
    await selectTemplate(page);
    await page.getByPlaceholder('Entity name').fill('Test Startup');

    // Click create venture
    await page.getByRole('button', { name: /create venture/i }).click();

    // The questionnaire card should appear
    await expect(
      page.getByRole('heading', { name: /questionnaire/i })
    ).toBeVisible({ timeout: 15000 });

    // Question input fields should appear (each question has placeholder "Your answer…")
    const answerFields = page.getByPlaceholder(/your answer/i);
    await expect(answerFields.first()).toBeVisible({ timeout: 10000 });
  });

  test('questionnaire shows section labels as step indicators', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    // Fill in the new venture form
    await selectTemplate(page);
    await page.getByPlaceholder('Entity name').fill('Test Startup');

    // Click create venture
    await page.getByRole('button', { name: /create venture/i }).click();

    // Wait for questionnaire to load
    await expect(
      page.getByRole('heading', { name: /questionnaire/i })
    ).toBeVisible({ timeout: 15000 });

    // Section headings serve as progress steps — saas_b2b plan includes
    // "Revenue Streams", "Go-to-Market", "Unit Economics", "USP" etc.
    // Assert at least one section label is visible
    const sectionLabels = [
      /revenue streams/i,
      /go.to.market/i,
      /unit economics/i,
      /working capital/i,
      /usp/i,
      /capacity/i,
      /costs/i,
    ];

    let foundSection = false;
    for (const pattern of sectionLabels) {
      const el = page.getByText(pattern);
      const count = await el.count();
      if (count > 0) {
        await expect(el.first()).toBeVisible({ timeout: 5000 });
        foundSection = true;
        break;
      }
    }
    expect(foundSection, 'At least one questionnaire section label should be visible as a step indicator').toBe(true);
  });

  test('multiple question fields are present covering different questionnaire steps', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    // Fill in the new venture form
    await selectTemplate(page);
    await page.getByPlaceholder('Entity name').fill('Test Startup');

    // Click create venture
    await page.getByRole('button', { name: /create venture/i }).click();

    // Wait for questionnaire to load
    await expect(
      page.getByRole('heading', { name: /questionnaire/i })
    ).toBeVisible({ timeout: 15000 });

    // There should be multiple answer fields (multiple questions across sections)
    const answerFields = page.getByPlaceholder(/your answer/i);
    const fieldCount = await answerFields.count();
    expect(fieldCount, 'Questionnaire should have multiple question input fields').toBeGreaterThan(1);
  });

  test('Save answers and Generate draft buttons are visible in questionnaire', async ({ page }) => {
    await login(page);

    await page.goto(`${BASE}/ventures`);
    await expect(page).toHaveURL(`${BASE}/ventures`, { timeout: 10000 });

    // Fill in the new venture form
    await selectTemplate(page);
    await page.getByPlaceholder('Entity name').fill('Test Startup');

    // Click create venture
    await page.getByRole('button', { name: /create venture/i }).click();

    // Wait for questionnaire to load
    await expect(
      page.getByRole('heading', { name: /questionnaire/i })
    ).toBeVisible({ timeout: 15000 });

    // Save answers button
    await expect(
      page.getByRole('button', { name: /save answers/i })
    ).toBeVisible({ timeout: 10000 });

    // Generate draft button
    await expect(
      page.getByRole('button', { name: /generate draft/i })
    ).toBeVisible({ timeout: 10000 });
  });
});
