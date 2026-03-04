// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";

test.describe("Public Chat Panel", () => {
    test("should show chat FAB on landing page", async ({ page }) => {
        await page.goto("/");
        const chatFab = page.locator('button[aria-label="Open AI chat assistant"]');
        await expect(chatFab).toBeVisible({ timeout: 10_000 });
    });

    test("should open public chat panel when clicking FAB", async ({ page }) => {
        await page.goto("/");
        const chatFab = page.locator('button[aria-label="Open AI chat assistant"]');
        await expect(chatFab).toBeVisible({ timeout: 10_000 });

        await chatFab.click();

        const chatPanel = page.locator('aside[aria-label="AI Chat Assistant"]');
        await expect(chatPanel).toBeVisible();
    });

    test("should show suggestion chips in empty public chat", async ({ page }) => {
        await page.goto("/");
        const chatFab = page.locator('button[aria-label="Open AI chat assistant"]');
        await expect(chatFab).toBeVisible({ timeout: 10_000 });
        await chatFab.click();

        const suggestion = page.getByRole("button", { name: /What loan products/ });
        await expect(suggestion).toBeVisible();
    });

    test("should close public chat panel via close button", async ({ page }) => {
        await page.goto("/");
        const chatFab = page.locator('button[aria-label="Open AI chat assistant"]');
        await expect(chatFab).toBeVisible({ timeout: 10_000 });
        await chatFab.click();

        const chatPanel = page.locator('aside[aria-label="AI Chat Assistant"]');
        await expect(chatPanel).toBeVisible();

        await page.locator('button[aria-label="Close chat"]').click();
        await expect(chatFab).toBeVisible();
    });

    test("should open chat via Explore Products button on hero", async ({ page }) => {
        await page.goto("/");
        const exploreBtn = page.getByRole("button", { name: "Explore Products" });
        await exploreBtn.click();

        const chatPanel = page.locator('aside[aria-label="AI Chat Assistant"]');
        await expect(chatPanel).toBeVisible();
    });
});
