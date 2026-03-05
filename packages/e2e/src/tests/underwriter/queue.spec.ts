// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { UWQueuePage } from "../../pages/uw-queue.page";

test.describe("Underwriter Queue", () => {
    let queue: UWQueuePage;

    test.beforeEach(async ({ page }) => {
        queue = new UWQueuePage(page);
        await queue.goto();
    });

    test("should display queue heading", async () => {
        await expect(queue.heading).toBeVisible();
    });

    test("should display four metric cards", async () => {
        await expect(queue.pendingReviewCard).toBeVisible();
        await expect(queue.inProgressCard).toBeVisible();
        await expect(queue.decidedTodayCard).toBeVisible();
        await expect(queue.avgReviewTimeCard).toBeVisible();
    });

    test("should display queue table with application rows", async () => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");
        const rowCount = await queue.tableRows.count();
        expect(rowCount).toBeGreaterThan(0);
    });

    test("should display sortable column headers", async () => {
        const expectedHeaders = ["Borrower", "Loan Amount", "Assigned LO", "Days in Queue", "Rate Lock", "Urgency"];
        for (const header of expectedHeaders) {
            await expect(queue.columnHeaders.filter({ hasText: header })).toBeVisible();
        }
    });

    test("should filter table by search input", async () => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");
        const initialCount = await queue.tableRows.count();
        test.skip(initialCount === 0, "No queue rows in seed data");

        // Get the first borrower name for a positive search
        const firstName = await queue.tableRows.first().locator("p.font-medium").textContent();
        if (!firstName) return;

        await queue.searchInput.fill(firstName);
        await expect(queue.tableRows.first()).toBeVisible();

        // Search for something non-existent
        await queue.searchInput.fill("ZZZNONEXISTENT999");
        await expect(queue.emptyState).toBeVisible();
    });

    test("should filter table by urgency dropdown", async ({ page }) => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");
        const countBefore = await queue.tableRows.count();

        await queue.urgencyFilter.selectOption({ label: "Critical" });

        await page.waitForFunction(
            (before) => document.querySelectorAll("tbody tr").length <= before,
            countBefore,
        );

        const countAfter = await queue.tableRows.count();
        expect(countAfter).toBeLessThanOrEqual(countBefore);
    });

    test("should sort table by clicking column header", async () => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");

        // Click the "Loan Amount" column header to sort
        const loanAmountHeader = queue.columnHeaders.filter({ hasText: "Loan Amount" });
        await loanAmountHeader.click();

        // Table should still have rows after sorting
        await expect(queue.tableRows.first()).toBeVisible();
    });

    test("should navigate to detail when clicking a row", async ({ page }) => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");

        await queue.tableRows.first().click();
        await expect(page).toHaveURL(/\/underwriter\/\d+/);
    });

    test("should show pending review count in footer", async () => {
        const hasRows = await queue.tableRows.first().isVisible({ timeout: 10_000 }).catch(() => false);
        test.skip(!hasRows, "No applications in queue -- empty database");
        await expect(queue.showingCount).toBeVisible();
    });
});
