// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { CeoDashboardPage } from "../../pages/ceo-dashboard.page";

let dashboard: CeoDashboardPage;

test.beforeEach(async ({ page }) => {
    dashboard = new CeoDashboardPage(page);
    await dashboard.goto();
    await expect(dashboard.heading).toBeVisible();
});

test.describe("CEO Executive Dashboard", () => {
    test("should display dashboard heading and subtitle", async () => {
        await expect(dashboard.heading).toHaveText("Executive Dashboard");
        await expect(dashboard.subtitle).toBeVisible();
    });

    // Skipped: the "AI Model Health" card is not implemented in the UI yet
    // (backend /api/analytics/model-monitoring exists, but there is no card component).
    test.skip("should display all 5 dashboard cards", async () => {
        await expect(dashboard.pipelineCard).toBeVisible();
        await expect(dashboard.denialCard).toBeVisible();
        await expect(dashboard.loPerformanceCard).toBeVisible();
        await expect(dashboard.modelHealthCard).toBeVisible();
        await expect(dashboard.auditCard).toBeVisible();
    });

    test("should display pipeline card with stage bars and stats", async () => {
        await expect(dashboard.pullThroughRate).toBeVisible();
        await expect(dashboard.avgDaysToClose).toBeVisible();
        await expect(dashboard.activeApplications).toBeVisible();
    });

    test("should display denial analysis card with bar chart and reasons", async () => {
        await expect(dashboard.overallDenialRate).toBeVisible();
        await expect(dashboard.topDenialReasons).toBeVisible();
    });

    test("should display LO performance card with table columns", async () => {
        const headers = dashboard.loTable.locator("thead th");
        await expect(headers.nth(0)).toHaveText("Name");
        await expect(headers.nth(1)).toHaveText("Active");
        await expect(headers.nth(2)).toHaveText("Closed");
        await expect(headers.nth(3)).toHaveText("Denial Rate");
    });

    test("should display at least one loan officer row", async () => {
        await expect(dashboard.loTableRows.first()).toBeVisible();
    });

    // Skipped: AI Model Health card is not implemented in the UI yet.
    test.skip("should display model health card with latency tiles or unavailable state", async () => {
        // Wait for model health data to load (skeleton replaced by real content)
        await expect(dashboard.latencyP50.or(dashboard.monitoringUnavailable)).toBeAttached({ timeout: 15_000 });
    });

    // Skipped: AI Model Health card is not implemented in the UI yet.
    test.skip("should display model health latency tiles when monitoring is available", async () => {
        await expect(dashboard.latencyP50.or(dashboard.monitoringUnavailable)).toBeAttached({ timeout: 15_000 });
        const p50Attached = await dashboard.latencyP50.count() > 0;
        if (p50Attached) {
            await expect(dashboard.latencyP95).toBeAttached();
            await expect(dashboard.latencyP99).toBeAttached();
        }
    });

    test("should display audit events card with table columns", async () => {
        await expect(dashboard.auditTableHeaders.nth(0)).toHaveText("Timestamp");
        await expect(dashboard.auditTableHeaders.nth(1)).toHaveText("Event Type");
        await expect(dashboard.auditTableHeaders.nth(2)).toHaveText("User");
        await expect(dashboard.auditTableHeaders.nth(3)).toHaveText("Description");
    });

    test("should display view full audit trail link", async () => {
        await expect(dashboard.viewFullAuditTrail).toBeVisible();
    });

    test("should display regulatory disclaimer footer", async () => {
        await expect(dashboard.disclaimer).toBeVisible();
    });
});
