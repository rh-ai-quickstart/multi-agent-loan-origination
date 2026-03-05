// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class LOPipelinePage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;

    // Metric cards
    readonly activeLoansCard: Locator;
    readonly inUnderwritingCard: Locator;
    readonly criticalUrgencyCard: Locator;
    readonly avgDaysCard: Locator;

    // Filters
    readonly searchInput: Locator;
    readonly stageFilter: Locator;
    readonly urgencyFilter: Locator;
    readonly stalledCheckbox: Locator;
    readonly columnHeaders: Locator;

    // Pipeline table
    readonly tableRows: Locator;
    readonly emptyState: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "Pipeline" });

        this.activeLoansCard = page.locator("div").filter({ has: page.getByText("Active Loans") }).first();
        this.inUnderwritingCard = page.locator("div").filter({ has: page.getByText("In Underwriting") }).first();
        this.criticalUrgencyCard = page.locator("div").filter({ has: page.getByText("Critical Urgency") }).first();
        this.avgDaysCard = page.locator("div").filter({ has: page.getByText("Avg Days in Stage") }).first();

        this.searchInput = page.getByPlaceholder("Search by borrower name or ID");
        // Identify each select by its unique first/default option text
        this.stageFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "All Stages" }) });
        this.urgencyFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "All Urgency" }) });
        this.stalledCheckbox = page.getByLabel("Stalled only");
        this.columnHeaders = page.locator("thead th");

        this.tableRows = page.locator("tbody tr");
        this.emptyState = page.getByText("No applications match your filters");
    }

    async goto(): Promise<void> {
        await this.page.goto("/loan-officer");
    }
}
