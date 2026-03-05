// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { SignInPage } from "../../pages/sign-in.page";
import { getPassword, IS_DEV_AUTH } from "../../helpers/env";

test.describe("Route Guards", () => {
    test("should redirect unauthenticated user from /borrower to /sign-in", async ({ page }) => {
        await page.goto("/borrower");
        await expect(page).toHaveURL(/\/sign-in/);
    });

    test("should redirect borrower away from /loan-officer", async ({ page }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.borrowerButton, getPassword());
        await page.waitForURL("**/borrower**");

        await page.goto("/loan-officer");

        // Dev auth redirects to persona's home; Keycloak logs out and redirects to sign-in
        if (IS_DEV_AUTH) {
            await expect(page).toHaveURL(/\/borrower/);
        } else {
            await expect(page).toHaveURL(/\/sign-in/);
        }
    });

    test("should redirect LO away from /borrower", async ({ page }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.loanOfficerButton, getPassword());
        await page.waitForURL("**/loan-officer**");

        await page.goto("/borrower");

        // Dev auth redirects to persona's home; Keycloak logs out and redirects to sign-in
        if (IS_DEV_AUTH) {
            await expect(page).toHaveURL(/\/loan-officer/);
        } else {
            await expect(page).toHaveURL(/\/sign-in/);
        }
    });
});
