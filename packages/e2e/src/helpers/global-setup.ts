// This project was developed with assistance from AI tools.

/**
 * Playwright global setup: polls API + UI health before running tests.
 * Optionally polls Keycloak health when not in dev auth mode.
 */

import { API_URL, BASE_URL, IS_DEV_AUTH, KEYCLOAK_URL } from "./env";

const MAX_RETRIES = 30;
const RETRY_DELAY_MS = 2_000;

async function pollHealth(url: string, label: string): Promise<void> {
    for (let i = 1; i <= MAX_RETRIES; i++) {
        try {
            const res = await fetch(url);
            if (res.ok) {
                console.log(`[global-setup] ${label} ready (attempt ${i})`);
                return;
            }
        } catch (e) {
            // connection refused -- keep retrying
            if (i > MAX_RETRIES - 3) {
                console.warn(`[global-setup] ${label} attempt ${i}/${MAX_RETRIES}: ${(e as Error).message}`);
            }
        }
        if (i < MAX_RETRIES) {
            await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
        }
    }
    throw new Error(
        `[global-setup] ${label} not ready after ${MAX_RETRIES} attempts at ${url}`,
    );
}

async function globalSetup(): Promise<void> {
    console.log("[global-setup] Waiting for services...");

    const checks = [
        pollHealth(`${API_URL}/health/`, "API"),
        pollHealth(BASE_URL, "UI"),
    ];

    if (!IS_DEV_AUTH) {
        // Keycloak start-dev may not expose /health/ready; fall back to base URL (302 redirect)
        checks.push(pollHealth(`${KEYCLOAK_URL}/realms/master`, "Keycloak"));
    }

    await Promise.all(checks);
    console.log("[global-setup] All services ready.");
}

export default globalSetup;
