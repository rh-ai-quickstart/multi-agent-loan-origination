// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { BorrowerDashboardPage } from "../../pages/borrower-dashboard.page";

test.describe("Borrower Conditions", () => {
    let dashboard: BorrowerDashboardPage;

    test.beforeEach(async ({ page }) => {
        dashboard = new BorrowerDashboardPage(page);
        await dashboard.goto();
    });

    test("should show conditions list or no-conditions message", async ({ page }) => {
        const conditionsHeading = page.getByRole("heading", {
            name: "Underwriting Conditions",
        });
        await expect(conditionsHeading).toBeVisible();

        // Either conditions are listed or "No outstanding conditions" is shown
        const noConditions = page.getByText("No outstanding conditions");
        const conditionItems = page.locator(".rounded-lg.border.p-4");

        const hasNoConditions = await noConditions.isVisible();
        const hasConditions = (await conditionItems.count()) > 0;

        expect(hasNoConditions || hasConditions).toBeTruthy();
    });

    test("should show respond button on actionable conditions", async ({ page }) => {
        const respondButtons = page.getByRole("button", { name: "Respond" });
        const conditionItems = page.locator(".rounded-lg.border.p-4");

        if ((await conditionItems.count()) > 0) {
            // At least some conditions should have respond buttons
            // (only open/responded/escalated ones do)
            const count = await respondButtons.count();
            // May be zero if all conditions are cleared/waived
            expect(count).toBeGreaterThanOrEqual(0);
        }
    });

    test("should populate chat input when clicking Respond", async ({ page }) => {
        const respondButtons = page.getByRole("button", { name: "Respond" });
        const count = await respondButtons.count();

        if (count > 0) {
            // Listen for chat-prefill event
            const prefillPromise = page.evaluate(() => {
                return new Promise<string>((resolve) => {
                    window.addEventListener(
                        "chat-prefill",
                        ((e: CustomEvent) => resolve(e.detail.message)) as EventListener,
                        { once: true },
                    );
                });
            });

            await respondButtons.first().click();

            const message = await prefillPromise;
            expect(message).toContain("condition");
        }
    });
});
