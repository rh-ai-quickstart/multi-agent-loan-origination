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

    test("should open disclosure modal on Review & Acknowledge click", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });

        if ((await reviewButton.count()) > 0) {
            await reviewButton.first().click();
            await expect(dashboard.disclosureModal).toBeVisible();
        }
    });

    test("should close disclosure modal via close button", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });

        if ((await reviewButton.count()) > 0) {
            await reviewButton.first().click();
            await expect(dashboard.disclosureModal).toBeVisible();

            await dashboard.modalCloseButton.click();
            await expect(dashboard.disclosureModal).not.toBeVisible();
        }
    });

    test("should trigger chat-prefill when acknowledging disclosure", async ({ page }) => {
        const reviewButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });

        if ((await reviewButton.count()) > 0) {
            await reviewButton.first().click();
            await expect(dashboard.disclosureModal).toBeVisible();

            // Listen for the chat-prefill event
            const prefillPromise = page.evaluate(() => {
                return new Promise<string>((resolve) => {
                    window.addEventListener(
                        "chat-prefill",
                        ((e: CustomEvent) => resolve(e.detail.message)) as EventListener,
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
