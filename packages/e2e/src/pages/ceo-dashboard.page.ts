// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class CeoDashboardPage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;
    readonly subtitle: Locator;

    // Refresh button
    readonly refreshButton: Locator;

    // Pipeline Overview card
    readonly pipelineCard: Locator;
    readonly pullThroughRate: Locator;
    readonly avgDaysToClose: Locator;
    readonly activeApplications: Locator;

    // Denial Analysis card
    readonly denialCard: Locator;
    readonly overallDenialRate: Locator;
    readonly topDenialReasons: Locator;

    // LO Performance card
    readonly loPerformanceCard: Locator;
    readonly loTable: Locator;
    readonly loTableRows: Locator;

    // Model Health card
    readonly modelHealthCard: Locator;
    readonly latencyP50: Locator;
    readonly latencyP95: Locator;
    readonly latencyP99: Locator;
    readonly monitoringUnavailable: Locator;

    // Audit Events card
    readonly auditCard: Locator;
    readonly auditTable: Locator;
    readonly auditTableHeaders: Locator;
    readonly auditTableRows: Locator;
    readonly viewFullAuditTrail: Locator;

    // Footer
    readonly disclaimer: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "Executive Dashboard" });
        this.subtitle = page.getByText("Summit Cap Financial");

        this.refreshButton = page.getByRole("button", { name: "Refresh" });

        this.pipelineCard = page.getByText("Pipeline Overview");
        this.pullThroughRate = page.getByText("Pull-Through Rate");
        this.avgDaysToClose = page.getByText("Avg Days to Close");
        this.activeApplications = page.getByText("Active Applications");

        this.denialCard = page.getByText("Denial Analysis");
        this.overallDenialRate = page.getByText("Overall Denial Rate");
        this.topDenialReasons = page.getByText("Top Denial Reasons");

        this.loPerformanceCard = page.getByText("Loan Officer Performance");
        this.loTable = page.locator("table").filter({ has: page.getByText("Denial Rate") });
        this.loTableRows = this.loTable.locator("tbody tr");

        this.modelHealthCard = page.getByText("AI Model Health");
        this.latencyP50 = page.getByText("P50");
        this.latencyP95 = page.getByText("P95");
        this.latencyP99 = page.getByText("P99");
        this.monitoringUnavailable = page.getByText("Monitoring Unavailable");

        this.auditCard = page.getByText("Recent Audit Events");
        this.auditTable = page.locator("table").filter({ has: page.getByText("Event Type") });
        this.auditTableHeaders = this.auditTable.locator("thead th");
        this.auditTableRows = this.auditTable.locator("tbody tr");
        this.viewFullAuditTrail = page.getByText("View Full Audit Trail");

        this.disclaimer = page.getByText("Summit Cap Financial is a fictional company");
    }

    async goto(): Promise<void> {
        await this.page.goto("/ceo");
    }
}
