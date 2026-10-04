import { expect, test } from "@playwright/test";

test("health check answers", async ({ request }) => {
  const r = await request.get("/healthz");
  expect(r.status()).toBe(200);
  expect(await r.json()).toEqual({ ok: true });
});

test("a visitor adds an item and sees it", async ({ page }) => {
  const title = `item ${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("Title").fill(title);
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByText(title)).toBeVisible();
});

test("admin needs an account; signing up opens it", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/sign-in/);
  await page.getByText("Create an account").click();
  await page.getByLabel("Email").fill(`owner${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("correct horse battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();
});
