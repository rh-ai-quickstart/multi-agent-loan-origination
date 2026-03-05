// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { UWDetailPage } from "../../pages/uw-detail.page";
import { UWQueuePage } from "../../pages/uw-queue.page";

test.describe("Underwriter Application Detail", () => {
    let detail: UWDetailPage;

    test.beforeEach(async ({ page }) => {
        // Navigate to queue first, then click into the first application
        const queue = new UWQueuePage(page);
        await queue.goto();

        await expect(queue.tableRows.first()).toBeVisible({ timeout: 10_000 });
        await queue.tableRows.first().click();
        await page.waitForURL(/\/underwriter\/\d+/);

        detail = new UWDetailPage(page);
    });

    test("should display breadcrumb with Queue link", async () => {
        await expect(detail.queueLink).toBeVisible();
    });

    test("should navigate back to queue via breadcrumb", async ({ page }) => {
        await detail.queueLink.click();
        await expect(page).toHaveURL(/\/underwriter$/);
    });

    test("should display Risk Assessment card with three metrics", async () => {
        await expect(detail.riskAssessmentHeading).toBeVisible();
        await expect(detail.creditMetric).toBeVisible();
        await expect(detail.capacityMetric).toBeVisible();
        await expect(detail.collateralMetric).toBeVisible();
    });

    test("should display Run Assessment button", async () => {
        await expect(detail.runAssessmentButton).toBeVisible();
    });

    test("should send chat-prefill when clicking Run Assessment", async ({ page }) => {
        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.runAssessmentButton.click();
        const result = await prefillPromise;
        expect(result.message).toContain("risk assessment");
    });

    test("should display Compliance Checks card", async () => {
        await expect(detail.complianceHeading).toBeVisible();
    });

    test("should display Conditions card", async () => {
        await expect(detail.conditionsHeading).toBeVisible();
    });

    test("should display Issue New Condition button", async () => {
        await expect(detail.issueConditionButton).toBeVisible();
    });

    test("should send chat-prefill when clicking Issue New Condition", async ({ page }) => {
        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.issueConditionButton.click();
        const result = await prefillPromise;
        expect(result.message).toContain("condition");
    });

    test("should display Preliminary Recommendation banner", async () => {
        await expect(detail.recommendationBanner).toBeVisible();
    });

    test("should display Make Decision panel with radio options", async () => {
        await expect(detail.decisionHeading).toBeVisible();
        await expect(detail.approveRadio).toBeVisible();
        await expect(detail.conditionalRadio).toBeVisible();
        await expect(detail.suspendRadio).toBeVisible();
        await expect(detail.denyRadio).toBeVisible();
    });

    test("should disable Record Decision button until decision and rationale are provided", async () => {
        await expect(detail.recordDecisionButton).toBeDisabled();

        // Select a decision
        await detail.approveRadio.check();
        await expect(detail.recordDecisionButton).toBeDisabled();

        // Add rationale
        await detail.rationaleInput.fill("Strong credit profile, low DTI");
        await expect(detail.recordDecisionButton).toBeEnabled();
    });

    test("should send chat-prefill when clicking Record Decision", async ({ page }) => {
        await detail.approveRadio.check();
        await detail.rationaleInput.fill("All conditions met");

        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.recordDecisionButton.click();
        const result = await prefillPromise;
        expect(result.message).toContain("Approve");
        expect(result.message).toContain("All conditions met");
    });

    test("should display Application Summary card", async () => {
        await expect(detail.appSummaryHeading).toBeVisible();
    });

    test("should display Compliance Knowledge Base card with topic chips", async () => {
        await expect(detail.complianceKBHeading).toBeVisible();
        const chipCount = await detail.kbTopicChips.count();
        expect(chipCount).toBe(6);
    });

    test("should send chat-prefill when clicking a KB topic chip", async ({ page }) => {
        const prefillPromise = page.evaluate(() => {
            return new Promise<{ message: string; autoSend: boolean }>((resolve, reject) => {
                const timeout = setTimeout(
                    () => reject(new Error("chat-prefill event not received within 5s")),
                    5_000,
                );
                window.addEventListener(
                    "chat-prefill",
                    ((e: CustomEvent) => {
                        clearTimeout(timeout);
                        resolve(e.detail);
                    }) as EventListener,
                    { once: true },
                );
            });
        });

        await detail.kbTopicChips.first().click();
        const result = await prefillPromise;
        expect(result.message).toContain("compliance KB");
    });

    test("should show application not found for invalid ID", async ({ page }) => {
        await page.goto("/underwriter/999999");
        await expect(detail.notFoundMessage).toBeVisible({ timeout: 10_000 });
    });
});
