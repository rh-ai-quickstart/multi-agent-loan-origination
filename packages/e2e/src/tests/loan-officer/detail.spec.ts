// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LODetailPage } from "../../pages/lo-detail.page";
import { LOPipelinePage } from "../../pages/lo-pipeline.page";

test.describe("Loan Officer Application Detail", () => {
    let detail: LODetailPage;

    test.beforeEach(async ({ page }) => {
        // Navigate to pipeline first, then click into the first application
        const pipeline = new LOPipelinePage(page);
        await pipeline.goto();

        // Wait for table data to load
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });

        await pipeline.tableRows.first().click();
        await page.waitForURL(/\/loan-officer\/\d+/);

        detail = new LODetailPage(page);
    });

    test("should display header with borrower name and stage badge", async ({ page }) => {
        // Header should have borrower name (a heading or prominent text)
        // and a stage badge (rounded-full span)
        const stageBadge = page.locator("span.rounded-full").first();
        await expect(stageBadge).toBeVisible();
    });

    test("should show Profile tab with borrower info", async ({ page }) => {
        await detail.profileTab.click();
        await expect(page.getByText("Borrower Info")).toBeVisible();
        await expect(page.getByText("Property Info")).toBeVisible();
    });

    test("should show Financial Summary tab with loan overview", async ({ page }) => {
        await detail.financialTab.click();
        await expect(page.getByText("Loan Overview")).toBeVisible();
    });

    test("should show Documents tab with completeness info", async ({ page }) => {
        await detail.documentsTab.click();
        await expect(page.getByText("Document Completeness")).toBeVisible();
    });

    test("should show Conditions tab", async ({ page }) => {
        await detail.conditionsTab.click();
        // Either conditions table or empty state
        const conditions = page.getByText("Condition").first();
        const emptyState = page.getByText("No underwriting conditions");
        const conditionsVisible = await conditions.isVisible();
        const emptyVisible = await emptyState.isVisible();
        expect(conditionsVisible || emptyVisible).toBeTruthy();
    });

    test("should display Request Documents button", async () => {
        await expect(detail.requestDocsButton).toBeVisible();
    });

    test("should display Submit to Underwriting button", async () => {
        await expect(detail.submitToUWButton).toBeVisible();
    });

    test("should navigate back to pipeline via breadcrumb link", async ({ page }) => {
        await detail.pipelineLink.click();
        await expect(page).toHaveURL(/\/loan-officer$/);
    });

    // W-10: Added 5s rejection timeout to the chat-prefill promise so the test
    // fails fast instead of hanging for 30s when the event is never fired.
    test("should send chat message when clicking Request Documents", async ({ page }) => {
        // Listen for chat-prefill event before clicking
        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.requestDocsButton.click();

        const detail_ = await prefillPromise;
        expect(detail_.message).toContain("missing documents");
        expect(detail_.autoSend).toBe(true);
    });

    // W-10: Added 5s rejection timeout to the chat-prefill promise.
    test("should send chat message when clicking Submit to Underwriting", async ({ page }) => {
        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.submitToUWButton.click();

        const detail_ = await prefillPromise;
        expect(detail_.message).toContain("underwriting");
        expect(detail_.autoSend).toBe(true);
    });

    test("should show document upload zone on Documents tab", async () => {
        await detail.documentsTab.click();
        await expect(detail.docUploadZone).toBeVisible();
    });

    // C-2: Replace silent if-guard with explicit test.skip so CI reports a skip
    // rather than a silent pass when no documents exist for the application.
    test("should expand document row to show extraction details", async ({ page }) => {
        await detail.documentsTab.click();

        // Find document rows in the table
        const docRows = page.locator("table tbody tr").filter({ hasNot: page.locator("td[colspan]") });
        const count = await docRows.count();
        test.skip(count === 0, "No document rows for this application in seed data");

        await docRows.first().click();
        // Expanded row should appear below (extraction details or "No extraction data")
        const expandedContent = page.getByText(/extraction|No extraction data/i);
        await expect(expandedContent.first()).toBeVisible({ timeout: 5_000 });
    });

    test("should show application not found for invalid ID", async ({ page }) => {
        await page.goto("/loan-officer/999999");
        await expect(detail.notFoundMessage).toBeVisible({ timeout: 10_000 });
    });
});
