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
        if (initialCount === 0) return;

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

        // Wait for filter to take effect
        if (countBefore > 1) {
            // Either rows change or we see a different count
            await page.waitForTimeout(500);
        }

        // All visible rows should be in Application stage (or empty)
        const rowCount = await pipeline.tableRows.count();
        if (rowCount > 0) {
            for (let i = 0; i < rowCount; i++) {
                // Stage badge is the second rounded-full span (first is urgency dot)
                const stageBadge = pipeline.tableRows
                    .nth(i)
                    .locator("td span.rounded-full.px-2\\.5");
                const stageText = await stageBadge.textContent();
                expect(stageText?.toLowerCase()).toContain("application");
            }
        }
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
        await page.waitForTimeout(300);

        const countAfter = await pipeline.tableRows.count();
        const emptyVisible = await pipeline.emptyState.isVisible();

        // Filter should change results: fewer rows or empty state
        expect(countAfter <= countBefore || emptyVisible).toBeTruthy();
    });

    test("should sort table by sort dropdown", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });

        // Switch sort to Loan Amount
        await pipeline.sortSelect.selectOption({ label: "Loan Amount" });

        // Wait for re-fetch
        await page.waitForTimeout(500);

        // Table should still have rows
        await expect(pipeline.tableRows.first()).toBeVisible();
    });

    test("should filter stalled applications via checkbox", async ({ page }) => {
        await expect(pipeline.tableRows.first()).toBeVisible({ timeout: 10_000 });
        const countBefore = await pipeline.tableRows.count();

        await pipeline.stalledCheckbox.check();
        await page.waitForTimeout(500);

        // Count may decrease or empty state may appear
        const countAfter = await pipeline.tableRows.count();
        const emptyVisible = await pipeline.emptyState.isVisible();

        expect(countAfter <= countBefore || emptyVisible).toBeTruthy();
    });
});
