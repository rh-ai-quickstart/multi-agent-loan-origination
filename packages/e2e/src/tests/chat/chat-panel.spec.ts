// This project was developed with assistance from AI tools.

import { test, expect, type Locator, type Page } from "@playwright/test";

// S-01: Extract repeated "ensure chat visible" pattern into a local helper.
async function ensureChatVisible(page: Page): Promise<Locator> {
    const textarea = page.locator('textarea[placeholder="Type your message..."]').first();
    if (!(await textarea.isVisible())) {
        const fab = page.locator('button[aria-label="Open chat assistant"]');
        if (await fab.isVisible()) await fab.click();
    }
    return textarea;
}

test.describe("Chat Panel", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/borrower");
    });

    test("should display chat sidebar on authenticated pages", async ({ page }) => {
        const chatSidebar = page.locator('aside[aria-label="Chat Assistant"]');
        // On desktop, sidebar should be visible; on mobile, FAB button instead
        const sidebarVisible = await chatSidebar.isVisible();
        const fabButton = page.locator('button[aria-label="Open chat assistant"]');
        const fabVisible = await fabButton.isVisible();

        expect(sidebarVisible || fabVisible).toBeTruthy();
    });

    test("should accept text in chat input", async ({ page }) => {
        const textarea = await ensureChatVisible(page);
        await textarea.fill("Hello, I need help with my mortgage application");
        await expect(textarea).toHaveValue("Hello, I need help with my mortgage application");
    });

    test("should display user message after sending", async ({ page }) => {
        const textarea = await ensureChatVisible(page);

        await textarea.fill("Test message for E2E");
        await page.locator('button[aria-label="Send message"]').click();

        // The user message should appear in the chat
        await expect(page.getByText("Test message for E2E")).toBeVisible({ timeout: 5_000 });
    });

    test("should populate input via chat-prefill event with autoSend false", async ({ page }) => {
        const textarea = await ensureChatVisible(page);

        // Dispatch chat-prefill event with autoSend: false
        await page.evaluate(() => {
            window.dispatchEvent(
                new CustomEvent("chat-prefill", {
                    detail: {
                        message: "Prefilled via E2E test",
                        autoSend: false,
                    },
                }),
            );
        });

        await expect(textarea).toHaveValue("Prefilled via E2E test");
    });

    test("should auto-send message via chat-prefill with autoSend true", async ({ page }) => {
        await ensureChatVisible(page);

        // Dispatch with autoSend: true -- message should appear in chat, not just in input
        await page.evaluate(() => {
            window.dispatchEvent(
                new CustomEvent("chat-prefill", {
                    detail: {
                        message: "Auto-sent E2E test message",
                        autoSend: true,
                    },
                }),
            );
        });

        // The message should appear as a user message bubble (auto-sent)
        // Use .first() since desktop sidebar and mobile panel may both render the text
        await expect(page.getByText("Auto-sent E2E test message").first()).toBeVisible({ timeout: 5_000 });
    });

    // C-1: Replaced vacuous `ws !== null || true` assertion. The test documents intent
    // clearly: we check whether a WebSocket connection was attempted, and skip rather
    // than trivially pass when the backend is unavailable.
    test("should attempt WebSocket connection", async ({ page }) => {
        // Monitor WebSocket connections
        const wsPromise = page.waitForEvent("websocket", { timeout: 10_000 }).catch(() => null);

        // Navigate to trigger WS connection
        await page.goto("/borrower");

        const ws = await wsPromise;
        // C-1 fix: assert the WS was actually attempted rather than always passing.
        // If the backend is not running this test should be fixed up, not vacuously passed.
        test.fixme(
            ws === null,
            "WebSocket connection depends on backend availability -- start the API server before running E2E tests",
        );
        expect(ws).not.toBeNull();
    });

    // C-1: Replaced `visible || true` with an explicit fixme when the state is non-deterministic.
    test("should show empty state with suggestion text before messages", async ({ page }) => {
        // On first load with no messages, chat should show the empty state
        const emptyPrompt = page.getByText("How can I help?");
        const textarea = await ensureChatVisible(page);
        const chatIsOpen = await textarea.isVisible();

        test.skip(!chatIsOpen, "Chat panel could not be opened");

        // C-1 fix: if empty state is not deterministic (e.g., prior test left messages),
        // mark as fixme rather than using a vacuous assertion.
        const visible = await emptyPrompt.isVisible().catch(() => false);
        test.fixme(
            !visible,
            "Empty state is not deterministic across test runs -- prior tests may have sent messages",
        );
        await expect(emptyPrompt).toBeVisible();
    });
});
