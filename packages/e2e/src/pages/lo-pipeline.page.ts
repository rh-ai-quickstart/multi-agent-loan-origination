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
    readonly sortSelect: Locator;
    readonly stalledCheckbox: Locator;

    // Pipeline table
    readonly tableRows: Locator;
    readonly emptyState: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "Pipeline" });

        this.activeLoansCard = page.getByText("Active Loans").locator("..");
        this.inUnderwritingCard = page.getByText("In Underwriting").locator("..");
        this.criticalUrgencyCard = page.getByText("Critical Urgency").locator("..");
        this.avgDaysCard = page.getByText("Avg Days in Stage").locator("..");

        this.searchInput = page.getByPlaceholder("Search by borrower name or ID");
        this.stageFilter = page.locator("select").nth(0);
        this.urgencyFilter = page.locator("select").nth(1);
        this.sortSelect = page.locator("select").nth(2);
        this.stalledCheckbox = page.getByLabel("Stalled only");

        this.tableRows = page.locator("tbody tr");
        this.emptyState = page.getByText("No applications match your filters");
    }

    async goto(): Promise<void> {
        await this.page.goto("/loan-officer");
    }
}
