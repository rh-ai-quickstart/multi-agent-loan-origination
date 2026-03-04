// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class LODetailPage {
    readonly page: Page;

    // Header
    readonly breadcrumb: Locator;
    readonly requestDocsButton: Locator;
    readonly submitToUWButton: Locator;

    // Tabs
    readonly profileTab: Locator;
    readonly financialTab: Locator;
    readonly documentsTab: Locator;
    readonly conditionsTab: Locator;

    // Profile tab
    readonly borrowerInfoCard: Locator;
    readonly propertyInfoCard: Locator;
    readonly loanDetailsCard: Locator;

    // Documents tab
    readonly docCompletenessCard: Locator;

    // Conditions tab
    readonly conditionsEmptyState: Locator;

    // Documents tab upload
    readonly docUploadZone: Locator;
    readonly docFileInput: Locator;

    // Breadcrumb link
    readonly pipelineLink: Locator;

    // Error state
    readonly notFoundMessage: Locator;

    constructor(page: Page) {
        this.page = page;

        this.breadcrumb = page.getByRole("navigation").filter({ hasText: "Pipeline" });
        this.pipelineLink = page.getByRole("link", { name: "Pipeline" });
        this.requestDocsButton = page.getByRole("button", { name: "Request Documents" });
        this.submitToUWButton = page.getByRole("button", { name: "Submit to Underwriting" });

        this.profileTab = page.getByRole("button", { name: "Profile" });
        this.financialTab = page.getByRole("button", { name: "Financial Summary" });
        this.documentsTab = page.getByRole("button", { name: "Documents", exact: true });
        this.conditionsTab = page.getByRole("button", { name: "Conditions" });

        this.borrowerInfoCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Borrower Info" }) }).first();
        this.propertyInfoCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Property Info" }) }).first();
        this.loanDetailsCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Loan Details" }) }).first();

        this.docCompletenessCard = page.locator("div").filter({ has: page.getByRole("heading", { name: "Document Completeness" }) }).first();

        this.conditionsEmptyState = page.getByText("No underwriting conditions");

        this.docUploadZone = page.getByText(/Drop files here|click to upload/);
        this.docFileInput = page.locator('input[type="file"]');

        this.notFoundMessage = page.getByText("Application not found");
    }

    async goto(applicationId: number): Promise<void> {
        await this.page.goto(`/loan-officer/${applicationId}`);
    }
}
