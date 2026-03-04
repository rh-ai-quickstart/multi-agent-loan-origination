// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { SignInPage } from "../../pages/sign-in.page";
import { getPassword } from "../../helpers/env";

test.describe("Sign Out", () => {
    test("should redirect to landing or sign-in after sign-out", async ({ page }) => {
        // Sign in first
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.borrowerButton, getPassword());
        await page.waitForURL("**/borrower**");

        // Find and click sign-out (dropdown menu or direct link)
        const signOutButton = page.getByText("Sign Out").or(page.getByText("Log Out"));
        if (await signOutButton.isVisible()) {
            await signOutButton.click();
        } else {
            // Try dropdown menu
            const avatar = page.locator('[data-testid="user-menu"]').or(
                page.getByRole("button", { name: /avatar|user|profile/i }),
            );
            if (await avatar.isVisible()) {
                await avatar.click();
                await page.getByText("Sign Out").or(page.getByText("Log Out")).click();
            }
        }

        // After sign-out, should be on landing or sign-in
        await expect(page).toHaveURL(/\/(sign-in)?$/);
    });

    test("should redirect to /sign-in when accessing /borrower after sign-out", async ({
        page,
    }) => {
        // Attempt to visit /borrower without auth
        await page.goto("/borrower");

        // Should be redirected to sign-in
        await expect(page).toHaveURL(/\/sign-in/);
    });

    test("should display user name and role badge in header when authenticated", async ({
        page,
    }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.borrowerButton, getPassword());
        await page.waitForURL("**/borrower**");

        // Header should show the user's name and role badge
        await expect(page.getByText("Sarah Mitchell")).toBeVisible();
        await expect(page.getByText("Borrower").first()).toBeVisible();
    });
});
