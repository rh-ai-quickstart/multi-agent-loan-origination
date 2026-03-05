// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class UWDetailPage {
    readonly page: Page;

    // Breadcrumb
    readonly queueLink: Locator;
    readonly breadcrumb: Locator;

    // Risk Assessment card
    readonly riskAssessmentHeading: Locator;
    readonly runAssessmentButton: Locator;
    readonly creditMetric: Locator;
    readonly capacityMetric: Locator;
    readonly collateralMetric: Locator;

    // Compliance Checks card
    readonly complianceHeading: Locator;
    readonly runChecksButton: Locator;

    // Conditions card
    readonly conditionsHeading: Locator;
    readonly issueConditionButton: Locator;

    // Recommendation banner
    readonly recommendationBanner: Locator;

    // Decision panel
    readonly decisionHeading: Locator;
    readonly approveRadio: Locator;
    readonly conditionalRadio: Locator;
    readonly suspendRadio: Locator;
    readonly denyRadio: Locator;
    readonly rationaleInput: Locator;
    readonly recordDecisionButton: Locator;

    // Application Summary card
    readonly appSummaryHeading: Locator;

    // Compliance KB card
    readonly complianceKBHeading: Locator;
    readonly kbTopicChips: Locator;

    // Error state
    readonly notFoundMessage: Locator;

    constructor(page: Page) {
        this.page = page;

        this.queueLink = page.getByRole("link", { name: "Queue" });
        this.breadcrumb = page.getByRole("navigation");

        this.riskAssessmentHeading = page.getByText("Risk Assessment").first();
        this.runAssessmentButton = page.getByRole("button", { name: /Run Assessment|Re-run/ });
        this.creditMetric = page.getByText("Credit").first();
        this.capacityMetric = page.getByText(/Capacity|DTI/).first();
        this.collateralMetric = page.getByText(/Collateral|LTV/).first();

        this.complianceHeading = page.getByText("Compliance Checks").first();
        this.runChecksButton = page.getByRole("button", { name: /Run Checks|Re-run/ }).nth(1);

        this.conditionsHeading = page.getByText("Conditions").first();
        this.issueConditionButton = page.getByRole("button", { name: "Issue New Condition" });

        this.recommendationBanner = page.getByText(/Preliminary Recommendation|Recommendation:/).first();

        this.decisionHeading = page.getByText("Make Decision");
        this.approveRadio = page.getByLabel("Approve", { exact: true });
        this.conditionalRadio = page.getByLabel("Approve w/ Conditions");
        this.suspendRadio = page.getByLabel("Suspend");
        this.denyRadio = page.getByLabel("Deny");
        this.rationaleInput = page.getByPlaceholder("Enter decision rationale...");
        this.recordDecisionButton = page.getByRole("button", { name: "Record Decision" });

        this.appSummaryHeading = page.getByText("Application Summary");
        this.complianceKBHeading = page.getByText("Compliance Knowledge Base");
        this.kbTopicChips = page.locator("button").filter({ hasText: /ECOA|ATR|TRID|PMI|FHA|Fannie Mae/ });

        this.notFoundMessage = page.getByText("Application not found");
    }

    async goto(applicationId: number): Promise<void> {
        await this.page.goto(`/underwriter/${applicationId}`);
    }
}
