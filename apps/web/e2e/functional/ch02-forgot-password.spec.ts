import { test, expect } from "@playwright/test";
import { BASE_URL } from "./fixtures/test-constants";

const BASE = BASE_URL;

test.describe("ch02 — Forgot Password", () => {
  test("forgot-password link is visible on login page", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    const link = page.getByRole("link", { name: /forgot password/i });
    await expect(link).toBeVisible();
  });

  test("forgot-password link navigates to /forgot-password", async ({
    page,
  }) => {
    await page.goto(`${BASE}/login`);
    await page.getByRole("link", { name: /forgot password/i }).click();
    await page.waitForURL("**/forgot-password", { timeout: 10_000 });
    expect(page.url()).toContain("/forgot-password");
  });

  test("forgot-password page has email input and submit button", async ({
    page,
  }) => {
    await page.goto(`${BASE}/forgot-password`);
    await expect(
      page.getByRole("heading", { name: /reset your password/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /send reset link/i }),
    ).toBeVisible();
  });

  test("forgot-password page has back to sign-in link", async ({ page }) => {
    await page.goto(`${BASE}/forgot-password`);
    const link = page.getByRole("link", { name: /sign in/i });
    await expect(link).toBeVisible();
  });
});
