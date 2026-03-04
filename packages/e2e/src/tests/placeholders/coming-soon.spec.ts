// This project was developed with assistance from AI tools.

import { test, expect } from "@playwright/test";
import { SignInPage } from "../../pages/sign-in.page";
import { getPassword } from "../../helpers/env";

test.describe("Placeholder Pages", () => {
    test("should show Coming Soon on /underwriter", async ({ page }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.underwriterButton, getPassword());
        await page.waitForURL("**/underwriter**");

        await expect(page.getByText("Coming Soon")).toBeVisible();
    });

    test("should show Coming Soon on /ceo", async ({ page }) => {
        const signIn = new SignInPage(page);
        await signIn.goto();
        await signIn.signInAs(signIn.ceoButton, getPassword());
        await page.waitForURL("**/ceo**");

        await expect(page.getByText("Coming Soon")).toBeVisible();
    });
});
