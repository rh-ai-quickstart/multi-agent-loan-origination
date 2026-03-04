// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { SignInPage } from "../../pages/sign-in.page";
import { getPassword } from "../../helpers/env";

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

        // Should be redirected back to borrower's home
        await expect(page).toHaveURL(/\/borrower/);
    });

    test("should redirect LO away from /borrower", async ({ page }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.loanOfficerButton, getPassword());
        await page.waitForURL("**/loan-officer**");

        await page.goto("/borrower");

        // Should be redirected back to LO's home
        await expect(page).toHaveURL(/\/loan-officer/);
    });
});
