import { test, expect } from "@playwright/test";
test("Navigate to Home Page", async ({ page }) => {
    await page.goto("/"); 
    await expect(page).toHaveTitle("Manage a provider's data – GOV.UK");
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('heading', { name: 'Provider records' }).isVisible();
});