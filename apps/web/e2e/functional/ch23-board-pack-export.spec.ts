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
 * Navigates to a board pack detail page (first available pack).
 * Returns true if a pack was found and opened, false otherwise.
 */
async function navigateToBoardPack(
  page: Parameters<Parameters<typeof test>[1]>[0]['page'],
): Promise<boolean> {
  await page.goto(`${BASE}/board-packs`);
  await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
    timeout: 10000,
  });

  // Try clicking the first board pack in the list
  const packLinks = page.locator('ul li a, table tbody tr td a, [role="list"] [role="listitem"] a');
  const count = await packLinks.count();
  if (count > 0) {
    await packLinks.first().click();
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    return true;
  }

  // Also try any clickable card or row that might represent a pack
  const packCards = page.locator('[data-testid*="board-pack"], .board-pack-item').first();
  const hasCard = await packCards.isVisible({ timeout: 3000 }).catch(() => false);
  if (hasCard) {
    await packCards.click();
    await page.waitForLoadState('networkidle', { timeout: 10000 });
    return true;
  }

  return false;
}

/**
 * Attempts to open the export dialog/panel on the current page.
 * Looks for an Export button and clicks it if found.
 * Returns true if the export UI was triggered.
 */
async function openExportUI(
  page: Parameters<Parameters<typeof test>[1]>[0]['page'],
): Promise<boolean> {
  // Look for export button on the page
  const exportBtn = page
    .getByRole('button', { name: /export|download/i })
    .or(page.getByRole('link', { name: /export|download/i }))
    .first();
  const hasExport = await exportBtn.isVisible({ timeout: 5000 }).catch(() => false);
  if (hasExport) {
    await exportBtn.click();
    await page.waitForTimeout(1000);
    return true;
  }
  return false;
}

test.describe('ch23 — Board Pack Export', () => {
  test('export format options PDF, PPTX, HTML are visible', async ({ page }) => {
    await login(page);

    const reached = await navigateToBoardPack(page);

    if (reached) {
      // Try to open the export dialog
      await openExportUI(page);
    } else {
      // No packs in list — navigate directly to board-packs and try export from list
      await page.goto(`${BASE}/board-packs`);
      await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
        timeout: 10000,
      });
      await openExportUI(page);
    }

    // Assert all three export format options are visible
    // They may appear as buttons, radio inputs, labels, or list items
    const pdfOption = page
      .getByRole('button', { name: /^pdf$/i })
      .or(page.getByRole('radio', { name: /pdf/i }))
      .or(page.getByLabel(/pdf/i))
      .or(page.getByText(/\bpdf\b/i).first());

    const pptxOption = page
      .getByRole('button', { name: /^pptx$/i })
      .or(page.getByRole('radio', { name: /pptx/i }))
      .or(page.getByLabel(/pptx/i))
      .or(page.getByText(/\bpptx\b/i).first());

    const htmlOption = page
      .getByRole('button', { name: /^html$/i })
      .or(page.getByRole('radio', { name: /html/i }))
      .or(page.getByLabel(/html/i))
      .or(page.getByText(/\bhtml\b/i).first());

    await expect(pdfOption.first()).toBeVisible({ timeout: 10000 });
    await expect(pptxOption.first()).toBeVisible({ timeout: 10000 });
    await expect(htmlOption.first()).toBeVisible({ timeout: 10000 });
  });

  test('Download or Export button is present on board pack', async ({ page }) => {
    await login(page);

    const reached = await navigateToBoardPack(page);

    if (!reached) {
      // No packs — check the board-packs list page for any export affordance
      await page.goto(`${BASE}/board-packs`);
      await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
        timeout: 10000,
      });
    }

    // Assert a Download or Export button exists somewhere on the page
    const actionBtn = page
      .getByRole('button', { name: /download|export/i })
      .or(page.getByRole('link', { name: /download|export/i }));
    await expect(actionBtn.first()).toBeVisible({ timeout: 10000 });
  });

  test('export dialog shows after clicking export and contains action button', async ({ page }) => {
    await login(page);

    const reached = await navigateToBoardPack(page);

    if (reached) {
      const opened = await openExportUI(page);

      if (opened) {
        // After opening export UI, a Download/Generate button should appear
        const confirmBtn = page
          .getByRole('button', { name: /download|generate|export/i })
          .or(page.getByRole('link', { name: /download|generate/i }));
        await expect(confirmBtn.first()).toBeVisible({ timeout: 10000 });
      } else {
        // Export button not found — still assert it exists as the spec requires it
        const exportBtn = page
          .getByRole('button', { name: /export|download/i })
          .or(page.getByRole('link', { name: /export|download/i }));
        await expect(exportBtn.first()).toBeVisible({ timeout: 10000 });
      }
    } else {
      // No board pack to open — assert export button exists on the list page
      await page.goto(`${BASE}/board-packs`);
      await page.waitForFunction(() => !document.body.innerText.includes('Loading'), {
        timeout: 10000,
      });
      const exportBtn = page
        .getByRole('button', { name: /export|download/i })
        .or(page.getByRole('link', { name: /export|download/i }));
      await expect(exportBtn.first()).toBeVisible({ timeout: 10000 });
    }
  });
});
