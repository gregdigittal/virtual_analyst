import { test, expect } from '@playwright/test';
import { TEST_USER } from './fixtures/test-constants';

const BASE = 'https://www.virtual-analyst.ai';

async function login(page: Parameters<Parameters<typeof test>[1]>[0]['page']) {
  await page.goto(`${BASE}/login`);
  await page.getByRole('textbox', { name: /email/i }).fill(TEST_USER.email);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
}

/**
 * Attempts to navigate to any board-pack builder page available.
 * Returns true if the builder page was reached.
 */
async function navigateToBuilder(
  page: Parameters<Parameters<typeof test>[1]>[0]['page'],
): Promise<boolean> {
  await page.goto(`${BASE}/board-packs`);
  await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
    timeout: 10000,
  });

  // Check for existing board packs in the list
  const packItems = page.locator('ul li a');
  const count = await packItems.count();
  if (count > 0) {
    await packItems.first().click();
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    // Navigate to the builder from the detail page
    const builderLink = page.getByText(/edit report sections/i).first();
    const hasBuilderLink = await builderLink.isVisible({ timeout: 5000 }).catch(() => false);
    if (hasBuilderLink) {
      await builderLink.click();
      await page.waitForLoadState('networkidle', { timeout: 10000 });
      return true;
    }
  }
  return false;
}

test.describe('ch23 — Board Pack Builder', () => {
  test('Create button is visible on board packs list page', async ({ page }) => {
    await login(page);
    await page.goto(`${BASE}/board-packs`);
    await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
      timeout: 10000,
    });

    // The spec says users can click Create from the list page
    const createBtn = page
      .getByRole('button', { name: /create board pack|new board pack|create/i })
      .or(page.getByRole('link', { name: /create board pack|new board pack/i }));
    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('board pack builder shows run selection', async ({ page }) => {
    await login(page);

    // Try clicking Create on the list page first
    await page.goto(`${BASE}/board-packs`);
    await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
      timeout: 10000,
    });

    const createBtn = page
      .getByRole('button', { name: /create board pack|new board pack|create/i })
      .or(page.getByRole('link', { name: /create board pack|new board pack/i }))
      .first();
    const hasCreate = await createBtn.isVisible({ timeout: 5000 }).catch(() => false);
    if (hasCreate) {
      await createBtn.click();
      await page.waitForLoadState('networkidle', { timeout: 10000 });
    } else {
      // Fall back to existing pack builder
      await navigateToBuilder(page);
    }

    // Spec: users can select a source run
    const runField = page
      .getByLabel(/run/i)
      .or(page.getByRole('combobox', { name: /run/i }))
      .or(page.getByRole('listbox', { name: /run/i }))
      .or(page.getByText(/select.*run|source run|run:/i).first());
    await expect(runField.first()).toBeVisible({ timeout: 10000 });
  });

  test('board pack builder shows section selection controls', async ({ page }) => {
    await login(page);
    const reached = await navigateToBuilder(page);

    if (!reached) {
      // If no packs exist, at minimum the list page or builder URL should show section UI
      await page.goto(`${BASE}/board-packs`);
      await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
        timeout: 10000,
      });
    }

    // Spec: choose sections to include — Executive Summary, Income Statement, etc.
    // Builder shows "Available sections" heading and section labels with Add buttons
    const sectionControl = page
      .getByText(/available sections/i)
      .or(page.getByText(/executive summary/i))
      .or(page.getByText(/income statement/i))
      .or(page.getByRole('checkbox'))
      .or(page.getByRole('switch'));
    await expect(sectionControl.first()).toBeVisible({ timeout: 10000 });
  });

  test('board pack builder shows section ordering controls', async ({ page }) => {
    await login(page);
    const reached = await navigateToBuilder(page);

    if (!reached) {
      await page.goto(`${BASE}/board-packs`);
      await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
        timeout: 10000,
      });
    }

    // Spec: arrange section order — drag or arrow controls
    // Builder shows "Report order" heading and ↑↓ buttons (aria-label: Move up / Move down)
    const orderControl = page
      .getByRole('button', { name: /move up|move down/i })
      .or(page.getByLabel(/move up|move down/i))
      .or(page.getByText(/report order/i));
    await expect(orderControl.first()).toBeVisible({ timeout: 10000 });
  });
});
