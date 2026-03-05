// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LOPipelinePage } from "../../pages/lo-pipeline.page";

test.describe("Pipeline Keyboard Navigation", () => {
    let pipeline: LOPipelinePage;

    test.beforeEach(async ({ page }) => {
        pipeline = new LOPipelinePage(page);
        await pipeline.goto();
        // Wait for page to load, then skip if no data
        await expect(page.getByRole("heading", { name: "Pipeline" })).toBeVisible({ timeout: 10_000 });
        const hasRows = await pipeline.tableRows.first().isVisible({ timeout: 5_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in pipeline -- empty database");
    });

    test("should focus pipeline rows via Tab key", async ({ page }) => {
        // W-7: Tab through until we reach a table row. The cap of 40 accounts for
        // header nav, filters, dropdowns, checkboxes, and other focusable
        // elements before the table body. Increase if new controls are added.
        for (let i = 0; i < 40; i++) {
            await page.keyboard.press("Tab");
            const focused = page.locator("tbody tr:focus");
            if ((await focused.count()) > 0) {
                await expect(focused).toBeVisible();
                return;
            }
        }

        // If we couldn't reach a row via Tab, that's a failure
        expect(false).toBeTruthy();
    });

    test("should navigate to detail on Enter key", async ({ page }) => {
        // Focus the first row
        await pipeline.tableRows.first().focus();
        await page.keyboard.press("Enter");

        await expect(page).toHaveURL(/\/loan-officer\/\d+/);
    });

    test("should show visible focus indicator on rows", async ({ page }) => {
        await pipeline.tableRows.first().focus();

        // The row should have a visible focus ring (outline or ring class)
        const row = pipeline.tableRows.first();
        const outline = await row.evaluate((el) => {
            const styles = window.getComputedStyle(el);
            return styles.outlineStyle !== "none" || styles.boxShadow !== "none";
        });
        expect(outline).toBeTruthy();
    });
});
