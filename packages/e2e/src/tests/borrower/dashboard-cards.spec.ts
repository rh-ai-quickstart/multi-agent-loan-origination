// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { BorrowerDashboardPage } from "../../pages/borrower-dashboard.page";

test.describe("Borrower Dashboard Cards", () => {
    let dashboard: BorrowerDashboardPage;

    test.beforeEach(async ({ page }) => {
        dashboard = new BorrowerDashboardPage(page);
        await dashboard.goto();
    });

    test("should show status card with application number and stage", async ({ page }) => {
        // Either shows an active application heading or "No active application found"
        const appHeading = page.getByRole("heading", { name: /Application #/ });
        const noApp = page.getByText("No active application found");
        await expect(appHeading.or(noApp).first()).toBeVisible();
    });

    test("should show stage stepper with highlighted current step", async ({ page }) => {
        const hasApp = await page.getByText(/Application #/).isVisible();
        if (hasApp) {
            // Stage stepper has ring-highlighted dot for current stage
            await expect(page.locator(".ring-4").first()).toBeVisible();
        }
    });

    test("should display documents card", async () => {
        await expect(
            dashboard.page.getByRole("heading", { name: "Documents" }),
        ).toBeVisible();
    });

    test("should display conditions card", async ({ page }) => {
        // Either conditions list or "No outstanding conditions" message
        const conditionsHeading = page.getByRole("heading", {
            name: "Underwriting Conditions",
        });
        await expect(conditionsHeading).toBeVisible();
    });

    test("should display disclosures card", async () => {
        await expect(
            dashboard.page.getByRole("heading", { name: "Disclosures" }),
        ).toBeVisible();
    });

    test("should display rate lock or pre-qualification card", async ({ page }) => {
        const rateLock = page.getByRole("heading", { name: "Rate Lock" });
        const prequal = page.getByRole("heading", { name: "Pre-Qualification" });
        await expect(rateLock.or(prequal).first()).toBeVisible();
    });

    test("should display application summary with loan details", async ({ page }) => {
        const summaryHeading = page.getByRole("heading", {
            name: "Application Summary",
        });
        await expect(summaryHeading).toBeVisible();
    });

    test("should show loan amount in summary card", async ({ page }) => {
        const hasApp = await page.getByText(/Application #/).isVisible();
        if (hasApp) {
            // Summary card should display a formatted currency value
            const summaryCard = page.getByRole("heading", { name: "Application Summary" }).locator("../..");
            await expect(summaryCard.getByText(/\$[\d,]+/)).toBeVisible();
        }
    });

    test("should show document rows or empty message in documents card", async ({ page }) => {
        const docsHeading = page.getByRole("heading", { name: "Documents" });
        await expect(docsHeading).toBeVisible();

        // Documents card should have at least one of: document rows, missing warning, or "no docs" text
        const docsCard = docsHeading.locator("../..");
        const docRows = docsCard.locator(".divide-y > div");
        const noDocsText = docsCard.getByText("No documents uploaded yet");
        const missingWarning = docsCard.getByText("Missing documents:");

        // Wait a moment for async data to load
        await page.waitForTimeout(500);

        const hasRows = (await docRows.count()) > 0;
        const isEmpty = await noDocsText.isVisible().catch(() => false);
        const hasMissing = await missingWarning.isVisible().catch(() => false);

        expect(hasRows || isEmpty || hasMissing).toBeTruthy();
    });
});
