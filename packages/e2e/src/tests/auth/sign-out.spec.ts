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

        // The header renders a direct "Sign out" button (aria-label) on desktop viewports.
        // This is deterministic -- if it is not visible the test must fail clearly.
        const signOutButton = page.getByRole("button", { name: "Sign out" });
        await expect(signOutButton).toBeVisible({ timeout: 5_000 });
        await signOutButton.click();

        // After sign-out the app navigates to the landing page
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
