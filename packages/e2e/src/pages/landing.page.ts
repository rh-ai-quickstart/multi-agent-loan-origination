// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class LandingPage {
    readonly page: Page;
    readonly heroHeading: Locator;
    readonly getPreQualifiedLink: Locator;
    readonly exploreProductsButton: Locator;
    readonly brandingText: Locator;

    // Affordability calculator
    readonly calculatorForm: Locator;
    readonly incomeInput: Locator;
    readonly debtsInput: Locator;
    readonly downPaymentInput: Locator;
    readonly interestRateInput: Locator;
    readonly calculateButton: Locator;
    readonly estimatedBudget: Locator;
    readonly estimatedPayment: Locator;
    readonly calculatorError: Locator;
    readonly dtiWarning: Locator;
    readonly askAssistantButton: Locator;

    // Public chat
    readonly chatFab: Locator;
    readonly chatPanel: Locator;
    readonly chatCloseButton: Locator;
    readonly chatInput: Locator;
    readonly chatSuggestions: Locator;

    constructor(page: Page) {
        this.page = page;
        this.heroHeading = page.getByRole("heading", { level: 1 });
        this.getPreQualifiedLink = page.getByRole("link", { name: "Get Pre-Qualified" });
        this.exploreProductsButton = page.getByRole("button", { name: "Explore Products" });
        this.brandingText = page.getByText("Summit Cap Financial").first();

        this.calculatorForm = page.getByRole("form", { name: "Affordability calculator form" });
        this.incomeInput = page.locator("#gross_annual_income");
        this.debtsInput = page.locator("#monthly_debts");
        this.downPaymentInput = page.locator("#down_payment");
        this.interestRateInput = page.locator("#interest_rate");
        this.calculateButton = page.getByRole("button", { name: "Calculate" });
        this.estimatedBudget = page.locator("div").filter({ has: page.getByText("Estimated Home Budget") }).first();
        this.estimatedPayment = page.locator("div").filter({ has: page.getByText("Est. Monthly Payment") }).first();
        this.calculatorError = page.getByRole("alert").filter({ hasText: "Unable to calculate" });
        this.dtiWarning = page.getByRole("alert").first();
        this.askAssistantButton = page.getByRole("button", { name: /Ask our assistant/ });

        this.chatFab = page.locator('button[aria-label="Open AI chat assistant"]');
        this.chatPanel = page.locator('aside[aria-label="AI Chat Assistant"]');
        this.chatCloseButton = page.locator('button[aria-label="Close chat"]');
        this.chatInput = page.locator('input[type="text"][placeholder="Type your message..."]');
        this.chatSuggestions = page.getByRole("button", { name: /What loan products/ });
    }

    async goto(): Promise<void> {
        await this.page.goto("/");
    }
}
