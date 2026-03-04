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

    // C-2: Replace silent if-guard with explicit test.skip so CI reports a skip
    // rather than a silent pass when there are no conditions in seed data.
    // C-1: Fixed trivially-true `toBeGreaterThanOrEqual(0)` -- changed to `toBeGreaterThan(0)`
    // so the assertion is meaningful when conditions are present.
    test("should show respond button on actionable conditions", async ({ page }) => {
        const conditionItems = page.locator(".rounded-lg.border.p-4");
        const conditionCount = await conditionItems.count();
        test.skip(conditionCount === 0, "No conditions in seed data");

        const respondButtons = page.getByRole("button", { name: "Respond" });
        const count = await respondButtons.count();
        // Conditions exist, so at least one should be actionable (open/responded/escalated).
        // Cleared or waived conditions do not show Respond, but if all were cleared the
        // seed data would have shown "No outstanding conditions" instead.
        expect(count).toBeGreaterThan(0);
    });

    // W-10: Added 5s rejection timeout to the chat-prefill promise so the test
    // fails fast instead of hanging for 30s when the event is never fired.
    test("should populate chat input when clicking Respond", async ({ page }) => {
        const respondButtons = page.getByRole("button", { name: "Respond" });
        const count = await respondButtons.count();

        if (count > 0) {
            // Listen for chat-prefill event
            const prefillPromise = page.evaluate(() => {
                return new Promise<string>((resolve, reject) => {
                    const timeout = setTimeout(
                        () => reject(new Error("chat-prefill event not received within 5s")),
                        5_000,
                    );
                    window.addEventListener(
                        "chat-prefill",
                        ((e: CustomEvent) => {
                            clearTimeout(timeout);
                            resolve(e.detail.message);
                        }) as EventListener,
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
