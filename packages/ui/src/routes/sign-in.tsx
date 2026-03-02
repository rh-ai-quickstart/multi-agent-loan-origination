// This project was developed with assistance from AI tools.

import { createFileRoute } from '@tanstack/react-router';
import { Logo } from '../components/logo/logo';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const Route = createFileRoute('/sign-in' as any)({
    component: SignIn,
});

function SignIn() {
    return (
        <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-slate-50 px-4 dark:bg-background">
            <div className="w-full max-w-sm">
                <div className="rounded-2xl border border-border bg-white p-8 shadow-md dark:bg-card">
                    <div className="mb-6 flex flex-col items-center gap-3 text-center">
                        <Logo />
                        <h1 className="font-display text-xl font-bold text-foreground">
                            Sign in to your account
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            Authentication will be available in a future release.
                        </p>
                    </div>
                    <div className="rounded-lg border border-border bg-muted/30 p-4 text-center text-sm text-muted-foreground">
                        This page is a placeholder. Full Keycloak-based authentication is
                        coming in Phase 2.
                    </div>
                </div>
            </div>
        </div>
    );
}
