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

    test("should display all 5 dashboard cards", async () => {
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

    test("should display model health card with latency tiles or unavailable state", async () => {
        const p50Visible = await dashboard.latencyP50.isVisible().catch(() => false);
        const unavailableVisible = await dashboard.monitoringUnavailable.isVisible().catch(() => false);
        expect(p50Visible || unavailableVisible).toBe(true);
    });

    test("should display model health latency tiles when monitoring is available", async () => {
        const p50Visible = await dashboard.latencyP50.isVisible().catch(() => false);
        if (p50Visible) {
            await expect(dashboard.latencyP95).toBeVisible();
            await expect(dashboard.latencyP99).toBeVisible();
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

    test("should have a refresh button that triggers data reload", async () => {
        await expect(dashboard.refreshButton).toBeVisible();
        await dashboard.refreshButton.click();
        await expect(dashboard.pipelineCard).toBeVisible();
    });

    test("should display regulatory disclaimer footer", async () => {
        await expect(dashboard.disclaimer).toBeVisible();
    });
});
