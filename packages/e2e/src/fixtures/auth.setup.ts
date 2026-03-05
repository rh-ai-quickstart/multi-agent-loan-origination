// This project was developed with assistance from AI tools.

import { test as setup, expect } from "@playwright/test";
import { getPassword, PERSONAS } from "../helpers/env";

/**
 * Sign in as a persona via the sign-in page demo buttons and save storageState.
 */
async function signInAndSave(
    page: import("@playwright/test").Page,
    persona: (typeof PERSONAS)[keyof typeof PERSONAS],
    storagePath: string,
): Promise<void> {
    await page.goto("/sign-in");

    // Wait for the page to be ready before interacting (prevents races on slow environments)
    await expect(page.locator("#email")).toBeVisible();

    // Click the persona demo button (fills email + password)
    await page.getByTitle(persona.title).click();

    // Verify email was filled
    await expect(page.locator("#email")).toHaveValue(persona.email);

    // Ensure password is filled (dev mode fills it; Keycloak mode may not)
    const passwordInput = page.locator("#password");
    const passwordValue = await passwordInput.inputValue();
    if (!passwordValue) {
        await passwordInput.fill(getPassword());
    }

    // Submit
    await page.locator('button[type="submit"]').click();

    // Wait for redirect to the persona's home route
    await page.waitForURL(`**${persona.homeRoute}**`);

    // Save auth state
    await page.context().storageState({ path: storagePath });
}

setup("sign in as borrower", async ({ page }) => {
    await signInAndSave(page, PERSONAS.borrower, ".auth/borrower.json");
});

setup("sign in as loan officer", async ({ page }) => {
    await signInAndSave(page, PERSONAS.loan_officer, ".auth/lo.json");
});

setup("sign in as underwriter", async ({ page }) => {
    await signInAndSave(page, PERSONAS.underwriter, ".auth/uw.json");
});

setup("sign in as ceo", async ({ page }) => {
    await signInAndSave(page, PERSONAS.ceo, ".auth/ceo.json");
});
