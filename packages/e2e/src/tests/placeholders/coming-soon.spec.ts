// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";

test.describe("Placeholder Pages", () => {
    test("should show Coming Soon on /underwriter", async ({ page }) => {
        // The borrower storageState won't have access to /underwriter,
        // so sign in as underwriter directly
        await page.goto("/sign-in");
        await page.getByTitle("Underwriter").click();
        await page.locator('button[type="submit"]').click();
        await page.waitForURL("**/underwriter**");

        await expect(page.getByText("Coming Soon")).toBeVisible();
    });

    test("should show Coming Soon on /ceo", async ({ page }) => {
        await page.goto("/sign-in");
        await page.getByTitle("CEO").click();
        await page.locator('button[type="submit"]').click();
        await page.waitForURL("**/ceo**");

        await expect(page.getByText("Coming Soon")).toBeVisible();
    });
});
