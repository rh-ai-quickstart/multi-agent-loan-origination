// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { LandingPage } from "../../pages/landing.page";

test.describe("Public Chat Panel", () => {
    let landing: LandingPage;

    test.beforeEach(async ({ page }) => {
        landing = new LandingPage(page);
        await landing.goto();
    });

    test("should show chat FAB on landing page", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
    });

    test("should open public chat panel when clicking FAB", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatPanel).toBeVisible();
    });

    test("should show suggestion chips in empty public chat", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatSuggestions).toBeVisible();
    });

    test("should close public chat panel via close button", async () => {
        await expect(landing.chatFab).toBeVisible({ timeout: 10_000 });
        await landing.chatFab.click();
        await expect(landing.chatPanel).toBeVisible();
        await landing.chatCloseButton.click();
        await expect(landing.chatFab).toBeVisible();
    });

    test("should open chat via Explore Products button on hero", async () => {
        await landing.exploreProductsButton.click();
        await expect(landing.chatPanel).toBeVisible();
    });
});
