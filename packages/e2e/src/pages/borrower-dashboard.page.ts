// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class BorrowerDashboardPage {
    readonly page: Page;

    // Status card
    readonly statusCard: Locator;
    readonly applicationHeading: Locator;

    // Dashboard cards
    readonly documentsCard: Locator;
    readonly conditionsCard: Locator;
    readonly disclosuresCard: Locator;
    readonly rateLockCard: Locator;
    readonly prequalCard: Locator;
    readonly summaryCard: Locator;

    // Documents
    readonly uploadZone: Locator;
    readonly fileInput: Locator;

    // Disclosures
    readonly acknowledgeButton: Locator;
    readonly disclosureModal: Locator;
    readonly modalCloseButton: Locator;
    readonly modalAcknowledgeButton: Locator;

    constructor(page: Page) {
        this.page = page;

        this.statusCard = page.locator("div").filter({ has: page.getByRole("heading", { name: /Application #/ }) }).first();
        this.applicationHeading = page.getByRole("heading", { name: /Application #/ });

        this.documentsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Documents" }) }).first();
        this.conditionsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Underwriting Conditions" }) }).first();
        this.disclosuresCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Disclosures" }) }).first();
        this.rateLockCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Rate Lock" }) }).first();
        this.prequalCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Pre-Qualification" }) }).first();
        this.summaryCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Application Summary" }) }).first();

        this.uploadZone = page.getByRole("button", { name: /Drop files here|click to upload/ });
        this.fileInput = page.locator('input[type="file"]');

        this.acknowledgeButton = page.getByRole("button", {
            name: "Review & Acknowledge",
        });
        this.disclosureModal = page.getByRole("dialog");
        this.modalCloseButton = page.getByRole("dialog").getByLabel("Close");
        this.modalAcknowledgeButton = page.getByRole("button", {
            name: "I Acknowledge",
        });
    }

    async goto(): Promise<void> {
        await this.page.goto("/borrower");
        // Wait for the dashboard to actually load (not redirect to sign-in)
        await this.page.waitForURL("**/borrower**", { timeout: 15_000 });
    }
}
