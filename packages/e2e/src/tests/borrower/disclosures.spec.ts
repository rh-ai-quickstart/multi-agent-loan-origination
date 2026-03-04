// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { BorrowerDashboardPage } from "../../pages/borrower-dashboard.page";

test.describe("Borrower Disclosures", () => {
    let dashboard: BorrowerDashboardPage;

    test.beforeEach(async ({ page }) => {
        dashboard = new BorrowerDashboardPage(page);
        await dashboard.goto();
    });

    test("should show disclosures list or all-acknowledged message", async ({ page }) => {
        const disclosuresHeading = page.getByRole("heading", { name: "Disclosures" });
        await expect(disclosuresHeading).toBeVisible();

        const allAcknowledged = page.getByText("All disclosures acknowledged");
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });

        const isAllDone = await allAcknowledged.isVisible();
        const hasPending = (await reviewButton.count()) > 0;

        expect(isAllDone || hasPending).toBeTruthy();
    });

    // C-2: Replace silent if-guard with explicit test.skip so CI reports a skip
    // rather than a silent pass when all disclosures are already acknowledged in seed data.
    test("should open disclosure modal on Review & Acknowledge click", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });
        test.skip((await reviewButton.count()) === 0, "No pending disclosures in seed data");

        await reviewButton.first().click();
        await expect(dashboard.disclosureModal).toBeVisible();
    });

    // C-2: Same skip pattern for the close modal test.
    test("should close disclosure modal via close button", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });
        test.skip((await reviewButton.count()) === 0, "No pending disclosures in seed data");

        await reviewButton.first().click();
        await expect(dashboard.disclosureModal).toBeVisible();

        await dashboard.modalCloseButton.click();
        await expect(dashboard.disclosureModal).not.toBeVisible();
    });

    // W-10: Added 5s rejection timeout to the chat-prefill promise so the test
    // fails fast instead of hanging for 30s when the event is never fired.
    test("should trigger chat-prefill when acknowledging disclosure", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });

        if ((await reviewButton.count()) > 0) {
            await reviewButton.first().click();
            await expect(dashboard.disclosureModal).toBeVisible();

            // Listen for the chat-prefill event
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

            await dashboard.modalAcknowledgeButton.click();

            const message = await prefillPromise;
            expect(message).toContain("acknowledge");
        }
    });
});
