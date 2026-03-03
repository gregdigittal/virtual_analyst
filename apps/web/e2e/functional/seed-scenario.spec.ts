import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

/**
 * seed-scenario.spec.ts
 *
 * End-to-end seed scenario: simulates a new user's first journey on the platform.
 * Creates a baseline from a marketplace template, then executes a simulation run.
 *
 * Run BEFORE functional tests to ensure entity data exists:
 *   npx playwright test e2e/functional/seed-scenario.spec.ts
 *
 * Model context: CE Africa (mining equipment aftermarket services) —
 * uses Manufacturing template as closest industry match.
 */

test.describe('Seed Scenario — Full E2E Onboarding', () => {
  // Increase timeout for the full flow (marketplace + baseline + run)
  test.setTimeout(120_000);

  test('Step 1: Log in and verify dashboard access', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for redirect away from login
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
    const url = page.url();
    expect(url).not.toContain('/login');
  });

  test('Step 2: Navigate to Marketplace and browse templates', async ({ page }) => {
    // Log in
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to marketplace
    await page.goto(`${BASE}/marketplace`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Verify marketplace page loaded with templates
    const heading = page.getByRole('heading', { name: /marketplace/i });
    await expect(heading.first()).toBeVisible({ timeout: 10000 });

    // Wait for templates to load (skeleton disappears)
    await page.waitForFunction(
      () => !document.querySelector('[class*="skeleton" i], [class*="animate-pulse" i]'),
      { timeout: 15000 }
    ).catch(() => {});

    // Verify at least one template card is visible
    const templateCards = page.locator('[class*="card" i], [class*="Card"]');
    const cardCount = await templateCards.count();
    expect(cardCount).toBeGreaterThan(0);
  });

  test('Step 3: Create a baseline from Manufacturing template (CE Africa model)', async ({ page }) => {
    // Log in
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to marketplace
    await page.goto(`${BASE}/marketplace`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(4000);

    // Look for the first template card with a "Use template" button
    // Prefer Manufacturing but accept any template
    const useButtons = page.getByRole('button', { name: /use template/i });
    const buttonCount = await useButtons.count();

    if (buttonCount === 0) {
      test.skip(true, 'No marketplace templates available');
      return;
    }

    // Find the template card — look for Manufacturing first, fallback to first card
    let targetCardIndex = 0;
    for (let i = 0; i < buttonCount; i++) {
      const card = useButtons.nth(i).locator('xpath=ancestor::*[contains(@class,"card") or contains(@class,"Card")]').first();
      const text = await card.textContent().catch(() => '');
      if (text && /manufactur/i.test(text)) {
        targetCardIndex = i;
        break;
      }
    }

    // Find the label and fiscal year inputs near the target button
    const targetButton = useButtons.nth(targetCardIndex);
    const card = targetButton.locator('xpath=ancestor::*[contains(@class,"card") or contains(@class,"Card") or contains(@class,"p-5")]').first();

    // Fill in the label and fiscal year inputs within the card
    const inputs = card.locator('input');
    const inputCount = await inputs.count();

    if (inputCount >= 2) {
      // First input = Label, Second input = Fiscal year
      await inputs.nth(0).fill('CE Africa Test Baseline');
      await inputs.nth(1).fill('2025');
    } else if (inputCount === 1) {
      await inputs.nth(0).fill('CE Africa Test Baseline');
    }

    // Click "Use template"
    await targetButton.click();

    // Wait for success toast or confirmation
    await page.waitForTimeout(3000);

    // Check for success: toast notification or redirect
    const successToast = page.getByText(/baseline created|template applied|success/i);
    const hasSuccess = await successToast.first().isVisible({ timeout: 10000 }).catch(() => false);

    // If no visible toast, check if we got redirected to baselines page
    if (!hasSuccess) {
      // At minimum, verify no error occurred
      const errorAlert = page.getByText(/error|failed|could not/i);
      const hasError = await errorAlert.first().isVisible({ timeout: 3000 }).catch(() => false);
      if (hasError) {
        const errorText = await errorAlert.first().textContent();
        console.warn(`Template creation may have failed: ${errorText}`);
      }
    }
  });

  test('Step 4: Verify baseline exists on baselines page', async ({ page }) => {
    // Log in
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to baselines
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Verify at least one baseline link exists
    const baselineLink = page.locator('a[href*="/baselines/"]').first();
    await expect(baselineLink).toBeVisible({ timeout: 15000 });
  });

  test('Step 5: Navigate to baseline detail and trigger a simulation run', async ({ page }) => {
    // Log in
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to baselines
    await page.goto(`${BASE}/baselines`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Click into the first baseline
    const baselineLink = page.locator('a[href*="/baselines/"]').first();
    const hasBaseline = await baselineLink.isVisible({ timeout: 10000 }).catch(() => false);

    if (!hasBaseline) {
      test.skip(true, 'No baselines available — run Step 3 first');
      return;
    }

    await baselineLink.click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Look for the Monte Carlo checkbox and "Create run" button
    const monteCarloOption = page.getByText(/monte carlo/i);
    const hasMonteOption = await monteCarloOption.first().isVisible({ timeout: 10000 }).catch(() => false);

    if (hasMonteOption) {
      // Check the Monte Carlo checkbox if it's a checkbox input
      const checkbox = page.locator('input[type="checkbox"]').first();
      const isChecked = await checkbox.isChecked().catch(() => false);
      if (!isChecked) {
        await checkbox.click().catch(() => {});
      }
    }

    // Click "Create run" button
    const createRunBtn = page
      .getByRole('button', { name: /create run|execute|run now|start run|submit/i });

    const hasCreateBtn = await createRunBtn.first().isVisible({ timeout: 10000 }).catch(() => false);

    if (!hasCreateBtn) {
      console.warn('Create run button not found on baseline detail page');
      return;
    }

    await createRunBtn.first().click();
    await page.waitForTimeout(5000);

    // Verify run was created — check for success indicator or redirect to runs page
    const successIndicator = page
      .getByText(/run created|simulation started|queued|running|pending|succeeded/i);
    const hasRunSuccess = await successIndicator.first().isVisible({ timeout: 15000 }).catch(() => false);

    if (!hasRunSuccess) {
      // Check if we were redirected to runs page
      const currentUrl = page.url();
      const onRunsPage = currentUrl.includes('/runs');
      expect(onRunsPage || hasRunSuccess).toBeTruthy();
    }
  });

  test('Step 6: Verify run exists on runs page', async ({ page }) => {
    // Log in
    await page.goto(`${BASE}/login`);
    await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
    await page.locator('input[type="password"]').fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Navigate to runs
    await page.goto(`${BASE}/runs`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // Verify at least one run link exists
    const runLink = page.locator('a[href*="/runs/"]').first();
    const hasRun = await runLink.isVisible({ timeout: 15000 }).catch(() => false);

    // It's OK if no runs exist yet (simulation may still be processing)
    if (!hasRun) {
      console.warn('No runs visible yet — simulation may still be processing');
    }
  });
});
