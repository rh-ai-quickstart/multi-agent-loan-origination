// This project was developed with assistance from AI tools.

import { createFileRoute } from '@tanstack/react-router';
import { BarChart3 } from 'lucide-react';

export const Route = createFileRoute('/_authenticated/ceo/')({
    component: CeoDashboard,
});

function CeoDashboard() {
    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-border bg-white p-16 shadow-sm dark:bg-slate-900">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#1e3a5f]/10">
                    <BarChart3 className="h-8 w-8 text-[#1e3a5f]" />
                </div>
                <h1 className="text-2xl font-bold text-foreground">CEO Dashboard</h1>
                <p className="text-muted-foreground">Coming Soon</p>
            </div>
        </div>
    );
}
