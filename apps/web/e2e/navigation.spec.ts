import { test, expect } from "@playwright/test";

test.describe("Navigation — public pages", () => {
  test("landing page renders hero and CTA", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /build better models/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /start free trial/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /sign in/i }).first(),
    ).toBeVisible();
  });

  test("landing page shows value propositions", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("LLM-assisted drafts")).toBeVisible();
    await expect(page.getByText("Monte Carlo & valuation")).toBeVisible();
    await expect(page.getByText("Built for teams")).toBeVisible();
    await expect(page.getByText("Audit-ready")).toBeVisible();
  });

  test("landing page hero CTA links to /signup", async ({ page }) => {
    await page.goto("/");
    const cta = page.getByRole("link", { name: /start free trial/i });
    await expect(cta).toHaveAttribute("href", "/signup");
  });

  test("navigate from landing to login", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /sign in/i }).first().click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test("navigate from landing to signup", async ({ page }) => {
    await page.goto("/");
    await page
      .getByRole("link", { name: /get started/i })
      .first()
      .click();
    await expect(page).toHaveURL(/\/signup/);
    await expect(
      page.getByRole("heading", { name: /create your account/i }),
    ).toBeVisible();
  });

  test("navigate from login to signup and back", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: /sign up/i }).click();
    await expect(page).toHaveURL(/\/signup/);

    await page.getByRole("link", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Navigation — footer", () => {
  test("footer shows branding and nav links", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(
      footer.getByText("Virtual Analyst", { exact: true }),
    ).toBeVisible();
    await expect(footer.getByRole("link", { name: /sign in/i })).toBeVisible();
    await expect(footer.getByRole("link", { name: /sign up/i })).toBeVisible();
  });
});
