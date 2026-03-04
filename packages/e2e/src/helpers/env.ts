// This project was developed with assistance from AI tools.

/**
 * E2E environment configuration and auth mode detection.
 */

export const BASE_URL = process.env.BASE_URL || "http://localhost:5173";
export const API_URL = process.env.API_URL || "http://localhost:8000";
export const KEYCLOAK_URL = process.env.KEYCLOAK_URL || "http://localhost:8080";
export const IS_DEV_AUTH = process.env.E2E_DEV_AUTH === "true";

export const DEV_PASSWORD = process.env.E2E_DEV_PASSWORD || "demo1234";
export const KEYCLOAK_PASSWORD = process.env.E2E_KEYCLOAK_PASSWORD || "demo";

export function getPassword(): string {
    return IS_DEV_AUTH ? DEV_PASSWORD : KEYCLOAK_PASSWORD;
}

export const PERSONAS = {
    borrower: {
        title: "Borrower",
        email: "sarah.mitchell@example.com",
        homeRoute: "/borrower",
    },
    loan_officer: {
        title: "Loan Officer",
        email: "james.torres@summit-cap.com",
        homeRoute: "/loan-officer",
    },
    underwriter: {
        title: "Underwriter",
        email: "maria.chen@summit-cap.com",
        homeRoute: "/underwriter",
    },
    ceo: {
        title: "CEO",
        email: "david.park@summit-cap.com",
        homeRoute: "/ceo",
    },
} as const;

export type PersonaKey = keyof typeof PERSONAS;
