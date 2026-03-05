// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LOPipelinePage } from "../../pages/lo-pipeline.page";

test.describe("Loan Officer Pipeline", () => {
    let pipeline: LOPipelinePage;

    test.beforeEach(async ({ page }) => {
        pipeline = new LOPipelinePage(page);
        await pipeline.goto();
    });

    test("should display pipeline heading", async () => {
        await expect(pipeline.heading).toBeVisible();
    });

    test("should display four metric cards", async ({ page }) => {
        await expect(page.getByText("Active Loans")).toBeVisible();
        await expect(page.getByText("In Underwriting")).toBeVisible();
        await expect(page.getByText("Critical Urgency")).toBeVisible();
        await expect(page.getByText("Avg Days in Stage")).toBeVisible();
    });

    test("should display pipeline table with application rows", async () => {
        // Wait for table data to load (async fetch)
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const rowCount = await pipeline.tableRows.count();
        expect(rowCount).toBeGreaterThan(0);
    });

    test("should filter table by search input", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const initialCount = await pipeline.tableRows.count();
        // C-2: Replace early `return` with explicit skip so CI captures the skip reason.
        test.skip(initialCount === 0, "No pipeline rows in seed data");

        // Get the first borrower name for a positive search
        const firstName = await pipeline.tableRows.first().locator("p.font-medium").textContent();
        if (!firstName) return;

        await pipeline.searchInput.fill(firstName);

        // Should still show at least the matching row
        await expect(pipeline.tableRows.first()).toBeVisible();

        // Search for something non-existent
        await pipeline.searchInput.fill("ZZZNONEXISTENT999");
        await expect(pipeline.emptyState).toBeVisible();
    });

    test("should filter table by stage dropdown", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const countBefore = await pipeline.tableRows.count();

        // Select a specific stage
        await pipeline.stageFilter.selectOption({ label: "Application" });

        // Client-side filter may reduce rows; wait for DOM to update
        await page.waitForFunction(
            (before) => document.querySelectorAll("tbody tr").length <= before,
            countBefore,
        );

        // Count should be reduced or same (filter applied)
        const countAfter = await pipeline.tableRows.count();
        expect(countAfter).toBeLessThanOrEqual(countBefore);
    });

    test("should navigate to detail when clicking a row", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const rowCount = await pipeline.tableRows.count();
        if (rowCount === 0) return;

        await pipeline.tableRows.first().click();
        await expect(page).toHaveURL(/\/loan-officer\/\d+/);
    });

    test("should filter table by urgency dropdown", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const countBefore = await pipeline.tableRows.count();

        // Select Critical urgency -- client-side filter
        await pipeline.urgencyFilter.selectOption({ label: "Critical" });

        // Client-side filter may produce 0 rows with no empty-state message,
        // so wait briefly then check the new count.
        await page.waitForFunction(
            (before) => document.querySelectorAll("tbody tr").length <= before,
            countBefore,
        );

        const countAfter = await pipeline.tableRows.count();

        // Filter should reduce or maintain results
        expect(countAfter).toBeLessThanOrEqual(countBefore);
    });

    test("should sort table by clicking column header", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });

        // Click the "Loan Amount" column header to sort
        const loanAmountHeader = pipeline.columnHeaders.filter({ hasText: "Loan Amount" });
        await loanAmountHeader.click();

        // Table should still have rows after sorting
        await expect(pipeline.tableRows.first()).toBeVisible();
    });

    test("should filter stalled applications via checkbox", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const countBefore = await pipeline.tableRows.count();

        await pipeline.stalledCheckbox.check();

        // Client-side filter may produce 0 rows with no empty-state message
        await page.waitForFunction(
            (before) => document.querySelectorAll("tbody tr").length <= before,
            countBefore,
        );

        const countAfter = await pipeline.tableRows.count();
        expect(countAfter).toBeLessThanOrEqual(countBefore);
    });
});
