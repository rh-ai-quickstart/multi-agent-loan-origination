// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { SignInPage } from "../../pages/sign-in.page";
import { getPassword, PERSONAS } from "../../helpers/env";

test.describe("Sign In", () => {
    let signIn: SignInPage;

    test.beforeEach(async ({ page }) => {
        signIn = new SignInPage(page);
        await signIn.goto();
    });

    test("should display four persona demo buttons", async () => {
        await expect(signIn.borrowerButton).toBeVisible();
        await expect(signIn.loanOfficerButton).toBeVisible();
        await expect(signIn.underwriterButton).toBeVisible();
        await expect(signIn.ceoButton).toBeVisible();
    });

    test("should fill borrower email when clicking Borrower button", async () => {
        await signIn.borrowerButton.click();
        await expect(signIn.emailInput).toHaveValue(PERSONAS.borrower.email);
    });

    test("should fill LO email when clicking Loan Officer button", async () => {
        await signIn.loanOfficerButton.click();
        await expect(signIn.emailInput).toHaveValue(PERSONAS.loan_officer.email);
    });

    test("should redirect borrower to /borrower after sign-in", async ({ page }) => {
        await signIn.signInAs(signIn.borrowerButton, getPassword());
        await page.waitForURL("**/borrower**");
        expect(page.url()).toContain("/borrower");
    });

    test("should redirect LO to /loan-officer after sign-in", async ({ page }) => {
        await signIn.signInAs(signIn.loanOfficerButton, getPassword());
        await page.waitForURL("**/loan-officer**");
        expect(page.url()).toContain("/loan-officer");
    });

    test("should show error on invalid credentials", async ({ page }) => {
        await signIn.emailInput.fill("invalid@example.com");
        await signIn.passwordInput.fill("wrong");
        await signIn.submitButton.click();

        await expect(signIn.errorMessage).toBeVisible({ timeout: 5_000 });
    });

    test("should redirect underwriter to /underwriter after sign-in", async ({ page }) => {
        await signIn.signInAs(signIn.underwriterButton, getPassword());
        await page.waitForURL("**/underwriter**");
        expect(page.url()).toContain("/underwriter");
    });

    test("should redirect CEO to /ceo after sign-in", async ({ page }) => {
        await signIn.signInAs(signIn.ceoButton, getPassword());
        await page.waitForURL("**/ceo**");
        expect(page.url()).toContain("/ceo");
    });

    test("should navigate back to landing when clicking close button", async ({ page }) => {
        await signIn.closeButton.click();
        await expect(page).toHaveURL(/\/$/);
    });

    test("should toggle password visibility", async () => {
        await signIn.passwordInput.fill("testpassword");
        await expect(signIn.passwordInput).toHaveAttribute("type", "password");

        await signIn.passwordToggle.click();
        await expect(signIn.passwordInput).toHaveAttribute("type", "text");

        await signIn.passwordToggle.click();
        await expect(signIn.passwordInput).toHaveAttribute("type", "password");
    });
});
