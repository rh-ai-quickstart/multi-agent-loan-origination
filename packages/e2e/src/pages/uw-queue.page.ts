// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class UWQueuePage {
    readonly page: Page;

    // Heading
    readonly heading: Locator;

    // Metric cards
    readonly pendingReviewCard: Locator;
    readonly inProgressCard: Locator;
    readonly decidedTodayCard: Locator;
    readonly avgReviewTimeCard: Locator;

    // Filters
    readonly searchInput: Locator;
    readonly urgencyFilter: Locator;

    // Queue table
    readonly columnHeaders: Locator;
    readonly tableRows: Locator;
    readonly emptyState: Locator;
    readonly showingCount: Locator;

    constructor(page: Page) {
        this.page = page;

        this.heading = page.getByRole("heading", { name: "Underwriting Queue" });

        this.pendingReviewCard = page.getByText("Pending Review", { exact: true });
        this.inProgressCard = page.getByText("In Progress");
        this.decidedTodayCard = page.getByText("Decided Today");
        this.avgReviewTimeCard = page.getByText("Avg Review Time");

        this.searchInput = page.getByPlaceholder("Search by borrower name or ID");
        this.urgencyFilter = page.locator("select").filter({ has: page.locator("option", { hasText: "All Urgency" }) });

        this.columnHeaders = page.locator("thead th");
        this.tableRows = page.locator("tbody tr");
        this.emptyState = page.getByText("No applications pending review.");
        this.showingCount = page.getByText(/Showing \d+ of \d+ pending reviews/);
    }

    async goto(): Promise<void> {
        await this.page.goto("/underwriter");
    }
}
