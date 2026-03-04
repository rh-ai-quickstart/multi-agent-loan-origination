// This project was developed with assistance from AI tools.

import type { Locator, Page } from "@playwright/test";

export class SignInPage {
    readonly page: Page;
    readonly emailInput: Locator;
    readonly passwordInput: Locator;
    readonly submitButton: Locator;
    readonly errorMessage: Locator;

    // Persona demo buttons
    readonly borrowerButton: Locator;
    readonly loanOfficerButton: Locator;
    readonly underwriterButton: Locator;
    readonly ceoButton: Locator;

    // Additional controls
    readonly closeButton: Locator;
    readonly passwordToggle: Locator;

    constructor(page: Page) {
        this.page = page;
        this.emailInput = page.locator("#email");
        this.passwordInput = page.locator("#password");
        this.submitButton = page.locator('button[type="submit"]');
        this.errorMessage = page.locator("p.text-red-700, p.text-red-400");

        this.borrowerButton = page.getByTitle("Borrower");
        this.loanOfficerButton = page.getByTitle("Loan Officer");
        this.underwriterButton = page.getByTitle("Underwriter");
        this.ceoButton = page.getByTitle("CEO");

        this.closeButton = page.getByLabel("Return to home");
        this.passwordToggle = page.getByLabel(/Show password|Hide password/);
    }

    async goto(): Promise<void> {
        await this.page.goto("/sign-in");
    }

    async signInAs(
        personaButton: Locator,
        password?: string,
    ): Promise<void> {
        await personaButton.click();
        if (password) {
            await this.passwordInput.fill(password);
        }
        await this.submitButton.click();
    }
}
