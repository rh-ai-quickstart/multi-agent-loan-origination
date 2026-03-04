// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LandingPage } from "../../pages/landing.page";

test.describe("Landing Page", () => {
    let landing: LandingPage;

    test.beforeEach(async ({ page }) => {
        landing = new LandingPage(page);
        await landing.goto();
    });

    test("should display hero heading with homeownership text", async () => {
        await expect(landing.heroHeading).toContainText("homeownership");
    });

    test("should have Get Pre-Qualified link navigating to /sign-in", async () => {
        await expect(landing.getPreQualifiedLink).toBeVisible();
        await expect(landing.getPreQualifiedLink).toHaveAttribute("href", /sign-in/);
    });

    test("should display Summit Cap Financial branding in header", async () => {
        await expect(landing.brandingText).toBeVisible();
    });

    test("should display Explore Products button", async () => {
        await expect(landing.exploreProductsButton).toBeVisible();
    });
});
