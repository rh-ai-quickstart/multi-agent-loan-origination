// This project was developed with assistance from AI tools.

import { createFileRoute } from '@tanstack/react-router';
import { Briefcase } from 'lucide-react';

export const Route = createFileRoute('/_authenticated/loan-officer/')({
    component: LoanOfficerDashboard,
});

function LoanOfficerDashboard() {
    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-border bg-white p-16 shadow-sm dark:bg-slate-900">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-purple-100">
                    <Briefcase className="h-8 w-8 text-purple-700" />
                </div>
                <h1 className="text-2xl font-bold text-foreground">Loan Officer Dashboard</h1>
                <p className="text-muted-foreground">Coming Soon</p>
            </div>
        </div>
    );
}
