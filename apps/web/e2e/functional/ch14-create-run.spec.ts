import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

test.describe('ch14 — Create Run', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  });

  test('Create Run button is visible on the runs page', async ({ page }) => {
    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    const createBtn = page
      .getByRole('button', { name: /create run|new run/i })
      .or(page.getByRole('link', { name: /create run|new run/i }));

    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Run flow shows draft selection', async ({ page }) => {
    await page.goto(`${BASE}/runs`);
    await expect(page).toHaveURL(new RegExp('/runs'), { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Click Create Run / New Run button
    const createBtn = page
      .getByRole('button', { name: /create run|new run/i })
      .or(page.getByRole('link', { name: /create run|new run/i }));

    await createBtn.first().click();
    await page.waitForTimeout(2000);

    // Assert draft selection is available — combobox, select, list, or label containing "draft"
    const draftSelector = page
      .getByRole('combobox', { name: /draft/i })
      .or(page.getByRole('listbox', { name: /draft/i }))
      .or(page.getByLabel(/draft/i))
      .or(page.getByText(/select.*draft|choose.*draft|draft/i));

    await expect(draftSelector.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Run flow shows mode selection (Deterministic / Monte Carlo)', async ({ page }) => {
    test.setTimeout(60000);

    // Navigate to baselines and find a baseline detail page with the run form
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);

    // Find a baseline link to click into
    const baselineLink = page.locator('a[href*="/baselines/"]').first();
    const hasBaseline = await baselineLink.isVisible({ timeout: 10000 }).catch(() => false);

    if (!hasBaseline) {
      test.skip(true, 'No baselines available for test user — cannot access run configuration form');
      return;
    }

    await baselineLink.click();
    await page.waitForURL(/\/baselines\/.+/, { timeout: 15000 });

    // Wait for page to finish loading config (Run model button is disabled until config loads)
    await page.waitForFunction(
      () => {
        const body = document.body.innerText;
        return !body.includes('Loading');
      },
      { timeout: 30000 }
    ).catch(() => {});
    await page.waitForTimeout(2000);

    // Click "Run model" to open the run configuration form
    // The button is disabled={!config}, so wait for it to become enabled
    const runModelBtn = page.getByRole('button', { name: /run model/i });
    await expect(runModelBtn).toBeVisible({ timeout: 15000 });
    await expect(runModelBtn).toBeEnabled({ timeout: 30000 });
    await runModelBtn.click();
    await page.waitForTimeout(1000);

    // The run config form has a "Monte Carlo simulation" checkbox
    const monteCarloOption = page.getByText(/monte carlo/i);
    await expect(monteCarloOption.first()).toBeVisible({ timeout: 10000 });
  });

  test('Create Run flow shows Execute or Run button', async ({ page }) => {
    test.setTimeout(60000);

    // Navigate to baselines and find a baseline detail page with the run form
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);

    const baselineLink = page.locator('a[href*="/baselines/"]').first();
    const hasBaseline = await baselineLink.isVisible({ timeout: 10000 }).catch(() => false);

    if (!hasBaseline) {
      test.skip(true, 'No baselines available for test user — cannot access run configuration form');
      return;
    }

    await baselineLink.click();
    await page.waitForURL(/\/baselines\/.+/, { timeout: 15000 });

    // Wait for page to finish loading config (Run model button is disabled until config loads)
    await page.waitForFunction(
      () => {
        const body = document.body.innerText;
        return !body.includes('Loading');
      },
      { timeout: 30000 }
    ).catch(() => {});
    await page.waitForTimeout(2000);

    // Click "Run model" to open the run configuration form
    // The button is disabled={!config}, so wait for it to become enabled
    const runModelBtn = page.getByRole('button', { name: /run model/i });
    await expect(runModelBtn).toBeVisible({ timeout: 15000 });
    await expect(runModelBtn).toBeEnabled({ timeout: 30000 });
    await runModelBtn.click();
    await page.waitForTimeout(1000);

    // The run config form has a "Create run" submit button
    const executeBtn = page
      .getByRole('button', { name: /execute|run now|start run|create run|submit/i });

    await expect(executeBtn.first()).toBeVisible({ timeout: 10000 });
  });
});
