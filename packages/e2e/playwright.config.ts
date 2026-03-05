// This project was developed with assistance from AI tools.

import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL || "http://localhost:5173";
const IS_CI = !!process.env.CI;

export default defineConfig({
    testDir: "./src/tests",
    fullyParallel: true,
    forbidOnly: IS_CI,
    retries: IS_CI ? 2 : 0,
    workers: IS_CI ? 1 : 2,
    reporter: IS_CI ? "blob" : "html",
    timeout: 30_000,

    expect: {
        timeout: 10_000,
    },

    use: {
        baseURL: BASE_URL,
        trace: "on-first-retry",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
    },

    // globalSetup health-checks verify that the full stack (UI + API + DB) is already
    // running before tests begin. Run `make test-e2e` (or `make test-e2e-setup` first)
    // rather than invoking playwright directly, so that services are up and seeded.
    globalSetup: "./src/helpers/global-setup.ts",

    projects: [
        // Auth setup -- runs first to produce storageState files
        {
            name: "auth-setup",
            testDir: "./src/fixtures",
            testMatch: "auth.setup.ts",
            use: { ...devices["Desktop Chrome"] },
        },

        // Public pages -- no auth needed
        {
            name: "public",
            testMatch: [
                "prospect/**/*.spec.ts",
                "auth/**/*.spec.ts",
            ],
            use: { ...devices["Desktop Chrome"] },
        },

        // Borrower tests -- use saved borrower auth
        {
            name: "borrower",
            testMatch: "borrower/**/*.spec.ts",
            dependencies: ["auth-setup"],
            use: {
                ...devices["Desktop Chrome"],
                storageState: ".auth/borrower.json",
            },
        },

        // Loan Officer tests -- use saved LO auth
        {
            name: "loan-officer",
            testMatch: "loan-officer/**/*.spec.ts",
            dependencies: ["auth-setup"],
            use: {
                ...devices["Desktop Chrome"],
                storageState: ".auth/lo.json",
            },
        },

        // Chat tests -- use borrower auth (chat is on all authenticated pages)
        {
            name: "chat",
            testMatch: "chat/**/*.spec.ts",
            dependencies: ["auth-setup"],
            use: {
                ...devices["Desktop Chrome"],
                storageState: ".auth/borrower.json",
            },
        },

        // Underwriter tests -- use saved UW auth
        {
            name: "underwriter",
            testMatch: "underwriter/**/*.spec.ts",
            dependencies: ["auth-setup"],
            use: {
                ...devices["Desktop Chrome"],
                storageState: ".auth/uw.json",
            },
        },

        // Placeholder tests -- sign in as UW/CEO directly (no stored auth)
        {
            name: "placeholders",
            testMatch: "placeholders/**/*.spec.ts",
            use: { ...devices["Desktop Chrome"] },
        },
    ],
});
