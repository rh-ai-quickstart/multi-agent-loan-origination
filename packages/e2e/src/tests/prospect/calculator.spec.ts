// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LandingPage } from "../../pages/landing.page";

test.describe("Affordability Calculator", () => {
    let landing: LandingPage;

    test.beforeEach(async ({ page }) => {
        landing = new LandingPage(page);
        await landing.goto();
    });

    test("should accept income, debts, and down payment inputs", async () => {
        await expect(landing.calculatorForm).toBeVisible();
        await expect(landing.incomeInput).toBeVisible();
        await expect(landing.debtsInput).toBeVisible();
        await expect(landing.downPaymentInput).toBeVisible();
    });

    test("should display estimated home budget after submission", async ({ page }) => {
        await landing.incomeInput.fill("120000");
        await landing.debtsInput.fill("500");
        await landing.downPaymentInput.fill("60000");
        await landing.calculateButton.click();

        // Wait for result to appear (currency format: $XXX,XXX)
        await expect(
            landing.estimatedBudget.getByText(/\$[\d,]+/),
        ).toBeVisible({ timeout: 10_000 });
    });

    test("should display estimated monthly payment after submission", async ({ page }) => {
        await landing.incomeInput.fill("120000");
        await landing.debtsInput.fill("500");
        await landing.downPaymentInput.fill("60000");
        await landing.calculateButton.click();

        await expect(
            landing.estimatedPayment.getByText(/\$[\d,]+/),
        ).toBeVisible({ timeout: 10_000 });
    });

    test("should show DTI warning for high-debt scenario", async ({ page }) => {
        await landing.incomeInput.fill("40000");
        await landing.debtsInput.fill("5000");
        await landing.downPaymentInput.fill("10000");
        await landing.calculateButton.click();

        // High DTI should show the blocking warning with amber styling
        await expect(page.getByText("Debt-to-Income Too High")).toBeVisible({ timeout: 10_000 });
    });

    test("should open chat when clicking Ask our assistant button", async () => {
        await expect(landing.askAssistantButton).toBeVisible();
        await landing.askAssistantButton.click();

        // Public chat panel should open
        await expect(landing.chatPanel).toBeVisible();
    });
});
